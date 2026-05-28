import asyncio
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from math import atan2, cos, pi, sin
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import utcnow
from app.models import FishingSpot, ForecastCache
from app.services.astronomy_provider import LocalAstronomyProvider
from app.services.fishing_score import (
    FishingContext,
    FishingConditions,
    calculate_fishing_score,
    list_species_profiles,
    serialize_fishing_context,
)
from app.services.marine_provider import OpenMeteoMarineProvider
from app.services.metno_weather_provider import MetNoWeatherProvider
from app.services.tide_provider import DerivedTideProvider
from app.services.weather_provider import OpenMeteoWeatherProvider


class ProviderUnavailableError(RuntimeError):
    pass


STALE_REFRESHING_WARNING = "Datos de cache caducada; actualizando pronostico en segundo plano."
STALE_PROVIDER_WARNING = "No se pudo actualizar ahora mismo; mostrando la ultima prevision guardada."
WEATHER_AVERAGE_FIELDS = {
    "temperature_2m": 2,
    "precipitation": 3,
    "precipitation_probability": 1,
    "pressure_msl": 2,
    "cloud_cover": 1,
    "wind_speed_10m": 2,
    "wind_gusts_10m": 2,
}
WEATHER_DIRECTION_FIELDS = {"wind_direction_10m"}


class ForecastService:
    provider_name = "open-meteo-combined-v6"

    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.weather_provider = OpenMeteoWeatherProvider(self.settings)
        self.weather_ensemble_providers = [MetNoWeatherProvider(self.settings)] if self.settings.weather_ensemble_enabled else []
        self.marine_provider = OpenMeteoMarineProvider(self.settings)
        self.astronomy_provider = LocalAstronomyProvider(self.settings)
        self.tide_provider = DerivedTideProvider()

    async def get_forecast(
        self,
        spot: FishingSpot,
        force_refresh: bool = False,
        fishing_context: FishingContext | None = None,
    ) -> dict:
        if not force_refresh:
            cached_forecast = self.get_cached_forecast(spot, fishing_context=fishing_context)
            if cached_forecast is not None:
                return cached_forecast

        try:
            weather_raw, marine_raw = await self._fetch_external_data(spot)
        except (httpx.HTTPError, RuntimeError) as exc:
            cached_forecast = self.get_cached_forecast(
                spot,
                fishing_context=fishing_context,
                allow_expired=True,
            )
            if cached_forecast is not None:
                cached_forecast.setdefault("meta", {})["warning"] = STALE_PROVIDER_WARNING
                return cached_forecast
            raise ProviderUnavailableError(f"No se pudo obtener el pronostico externo: {exc}") from exc

        forecast = self._build_response(spot, weather_raw, marine_raw, fishing_context)
        self._store_cache(spot.id, forecast)
        return forecast

    def get_cached_forecast(
        self,
        spot: FishingSpot,
        fishing_context: FishingContext | None = None,
        allow_expired: bool = False,
    ) -> dict | None:
        cache = self._get_valid_cache(spot)
        stale = False
        if cache is None and allow_expired:
            cache = self._get_latest_cache(spot)
            stale = cache is not None
        if cache is None:
            return None

        forecast = deepcopy(cache.raw_data)
        meta = forecast.setdefault("meta", {})
        meta["cached"] = True
        if stale:
            meta["stale"] = True
            meta["warning"] = STALE_REFRESHING_WARNING
        else:
            meta.pop("stale", None)
            if meta.get("warning") in {STALE_REFRESHING_WARNING, STALE_PROVIDER_WARNING}:
                meta.pop("warning", None)
        return self._rescore_forecast(forecast, fishing_context)

    async def _fetch_external_data(self, spot: FishingSpot) -> tuple[dict, dict]:
        weather, marine = await asyncio.gather(
            self._fetch_weather_data(spot),
            self.marine_provider.fetch(spot.latitude, spot.longitude, self.settings.forecast_days),
        )
        return weather, marine

    async def _fetch_weather_data(self, spot: FishingSpot) -> dict:
        providers = [self.weather_provider, *self.weather_ensemble_providers]
        results = await asyncio.gather(
            *[
                provider.fetch(spot.latitude, spot.longitude, self.settings.forecast_days)
                for provider in providers
            ],
            return_exceptions=True,
        )
        successes: list[tuple[str, dict]] = []
        failures: list[dict] = []
        for provider, result in zip(providers, results, strict=False):
            provider_name = getattr(provider, "provider_name", provider.__class__.__name__)
            if isinstance(result, Exception):
                failures.append({"provider": provider_name, "error": str(result)})
            else:
                successes.append((provider_name, result))

        if not successes:
            failure_text = "; ".join(f"{item['provider']}: {item['error']}" for item in failures)
            raise RuntimeError(f"No se pudo obtener meteorologia de ningun proveedor: {failure_text}")

        if len(successes) == 1:
            weather_raw = deepcopy(successes[0][1])
            weather_raw["_arcafish_weather_meta"] = {
                "provider": successes[0][0],
                "providers": [successes[0][0]],
                "ensemble": False,
                "failures": failures,
            }
            return weather_raw

        weather_raw = _merge_weather_payloads(successes)
        weather_raw["_arcafish_weather_meta"]["failures"] = failures
        return weather_raw

    def _build_response(
        self,
        spot: FishingSpot,
        weather_raw: dict,
        marine_raw: dict,
        fishing_context: FishingContext | None = None,
    ) -> dict:
        tz = ZoneInfo(self.settings.canary_timezone)
        weather_hourly = weather_raw.get("hourly") or {}
        marine_hourly = marine_raw.get("hourly") or {}
        weather_meta = weather_raw.get("_arcafish_weather_meta") or {}
        weather_times: list[str] = weather_hourly.get("time") or []
        marine_times: list[str] = marine_hourly.get("time") or []
        marine_index = {time_value: index for index, time_value in enumerate(marine_times)}

        tide_by_time = self.tide_provider.derive(
            marine_times,
            marine_hourly.get("sea_level_height_msl") or [],
        )
        dates = {_parse_local_datetime(time_value, tz).date() for time_value in weather_times}
        astronomy = self.astronomy_provider.get_days(spot.latitude, spot.longitude, dates)
        now_local = datetime.now(tz)
        today_local = now_local.date()

        hourly_rows: list[dict] = []
        for index, time_value in enumerate(weather_times):
            moment = _parse_local_datetime(time_value, tz)
            if moment.date() < today_local:
                continue

            marine_i = marine_index.get(time_value)
            astro = astronomy.get(moment.date())
            tide = tide_by_time.get(time_value)
            pressure = _series_value(weather_hourly, "pressure_msl", index)
            pressure_trend = None
            if index >= 3 and pressure is not None:
                previous_pressure = _series_value(weather_hourly, "pressure_msl", index - 3)
                if previous_pressure is not None:
                    pressure_trend = round(pressure - previous_pressure, 1)

            weather_code = _series_value(weather_hourly, "weather_code", index)
            is_day_value = _series_value(weather_hourly, "is_day", index)
            conditions = FishingConditions(
                datetime=moment,
                wind_speed_ms=_series_value(weather_hourly, "wind_speed_10m", index),
                wind_gust_ms=_series_value(weather_hourly, "wind_gusts_10m", index),
                wind_direction_deg=_series_value(weather_hourly, "wind_direction_10m", index),
                temperature_c=_series_value(weather_hourly, "temperature_2m", index),
                sea_surface_temperature_c=_series_value(marine_hourly, "sea_surface_temperature", marine_i),
                precipitation_mm=_series_value(weather_hourly, "precipitation", index),
                precipitation_probability=_series_value(weather_hourly, "precipitation_probability", index),
                pressure_hpa=pressure,
                pressure_trend_hpa=pressure_trend,
                cloud_cover_percent=_series_value(weather_hourly, "cloud_cover", index),
                wave_height_m=_series_value(marine_hourly, "wave_height", marine_i),
                wave_period_s=_series_value(marine_hourly, "wave_period", marine_i),
                wave_direction_deg=_series_value(marine_hourly, "wave_direction", marine_i),
                tide_state=tide.state if tide else None,
                tide_height_m=tide.height_m if tide else None,
                moon_phase=astro.moon_phase if astro else None,
                sunrise=astro.sunrise if astro else None,
                sunset=astro.sunset if astro else None,
                is_day=None if is_day_value is None else bool(is_day_value),
                weather_description=weather_code_description(weather_code),
            )
            general_score = calculate_fishing_score(conditions, "general")
            species_scores = {
                species["id"]: _serialize_score(calculate_fishing_score(conditions, species["id"], fishing_context))
                for species in list_species_profiles()
            }
            hourly_rows.append(
                {
                    "datetime": moment.isoformat(),
                    "weather_code": int(weather_code) if weather_code is not None else None,
                    "weather_description": conditions.weather_description,
                    "wind_speed_ms": _round(conditions.wind_speed_ms, 1),
                    "wind_gust_ms": _round(conditions.wind_gust_ms, 1),
                    "wind_direction_deg": _round(conditions.wind_direction_deg, 0),
                    "temperature_c": _round(conditions.temperature_c, 1),
                    "precipitation_mm": _round(conditions.precipitation_mm, 1),
                    "precipitation_probability": _round(conditions.precipitation_probability, 0),
                    "pressure_hpa": _round(conditions.pressure_hpa, 0),
                    "pressure_trend_hpa": _round(conditions.pressure_trend_hpa, 1),
                    "cloud_cover_percent": _round(conditions.cloud_cover_percent, 0),
                    "wave_height_m": _round(conditions.wave_height_m, 1),
                    "wave_period_s": _round(conditions.wave_period_s, 0),
                    "wave_direction_deg": _round(conditions.wave_direction_deg, 0),
                    "sea_surface_temperature_c": _round(conditions.sea_surface_temperature_c, 1),
                    "tide_state": conditions.tide_state or "sin datos",
                    "tide_height_m": _round(conditions.tide_height_m, 2),
                    "moon_phase": conditions.moon_phase,
                    "sunrise": astro.sunrise.isoformat() if astro else None,
                    "sunset": astro.sunset.isoformat() if astro else None,
                    "fishing_score": general_score.score,
                    "fishing_category": general_score.category,
                    "explanation": general_score.explanation,
                    "safety_alerts": general_score.safety_alerts,
                    "confidence": general_score.confidence,
                    "missing_fields": general_score.missing_fields,
                    "factor_scores": general_score.factor_scores,
                    "species_scores": species_scores,
                }
            )

        summary = self._summary(hourly_rows, now_local)
        fishing_context_data = serialize_fishing_context(fishing_context) if fishing_context else None
        return {
            "spot": {
                "id": spot.id,
                "name": spot.name,
                "latitude": spot.latitude,
                "longitude": spot.longitude,
                "notes": spot.notes,
                "method_contexts": spot.method_contexts,
            },
            "fishing_context": fishing_context_data,
            "summary": summary,
            "hourly": hourly_rows,
            "meta": {
                "provider": self.provider_name,
                "weather_provider": weather_meta.get("provider", self.weather_provider.provider_name),
                "weather_providers": weather_meta.get("providers", [self.weather_provider.provider_name]),
                "weather_ensemble": weather_meta.get("ensemble", False),
                "weather_provider_failures": weather_meta.get("failures", []),
                "marine_provider": self.marine_provider.provider_name,
                "astronomy_provider": self.astronomy_provider.provider_name,
                "cached": False,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "timezone": self.settings.canary_timezone,
                "forecast_days": self.settings.forecast_days,
                "limitations": [
                    "La marea se deriva de sea_level_height_msl de Open-Meteo Marine; no sustituye tablas oficiales de mareas.",
                    "La exposicion viento-costa queda preparada para una futura capa geoespacial de costa.",
                    "La distancia de lance se interpreta como distancia horizontal desde costa, no como profundidad.",
                    "El score general es un promedio ponderado de las proximas 24 horas desde el momento actual.",
                    "La tabla permite cambiar el intervalo de visualizacion sin volver a pedir datos al proveedor.",
                ],
                "fishing_context": fishing_context_data,
                "species_profiles": list_species_profiles(),
                "sources": [
                    "https://open-meteo.com/en/docs",
                    "https://open-meteo.com/en/docs/marine-weather-api",
                    "https://api.met.no/weatherapi/locationforecast/2.0/documentation",
                ],
            },
        }

    def _summary(self, hourly_rows: list[dict], now_local: datetime) -> dict:
        if not hourly_rows:
            return {
                "score": 0,
                "category": "Mala",
                "recommendation": "No hay datos horarios suficientes para calcular una ventana de pesca.",
                "safety_alerts": ["Pronostico incompleto."],
                "species": {},
            }

        next_24h = _rows_for_next_24h(hourly_rows, now_local)
        current_row = _current_or_first_row(hourly_rows, now_local)
        weights = _summary_weights(len(next_24h))
        summary_score = _weighted_rows(next_24h, "fishing_score", weights)
        summary_category = _score_category(summary_score)
        best = max(next_24h, key=lambda row: row["fishing_score"])
        alerts = list(
            dict.fromkeys(
                alert
                for row in next_24h
                for alert in row.get("safety_alerts", [])
            )
        )
        category_counts = Counter(row["fishing_category"] for row in next_24h)
        dominant_category = category_counts.most_common(1)[0][0] if category_counts else best["fishing_category"]
        best_dt = datetime.fromisoformat(best["datetime"])
        recommendation = (
            f"Base de calculo: proximas 24 h desde {datetime.fromisoformat(current_row['datetime']).strftime('%d/%m %H:%M')}. "
            f"Mejor ventana: {best_dt.strftime('%d/%m %H:%M')}."
        )
        return {
            "score": summary_score,
            "category": summary_category,
            "dominant_next_24h": dominant_category,
            "recommendation": recommendation,
            "best_datetime": best["datetime"],
            "best_explanation": best["explanation"],
            "best_score": best["fishing_score"],
            "current_datetime": current_row["datetime"],
            "current_score": current_row["fishing_score"],
            "current_wind_ms": current_row["wind_speed_ms"],
            "current_wave_m": current_row["wave_height_m"],
            "safety_alerts": alerts,
            "species": self._species_summary(next_24h, current_row, weights),
        }

    def _species_summary(self, next_24h: list[dict], current_row: dict, weights: list[float]) -> dict:
        summaries: dict[str, dict] = {}
        for species in list_species_profiles():
            species_id = species["id"]
            best_row = max(
                next_24h,
                key=lambda row: row["species_scores"][species_id]["score"],
            )
            score = _weighted_species_rows(next_24h, species_id, weights)
            summaries[species_id] = {
                "id": species_id,
                "name": species["name"],
                "description": species["description"],
                "score": score,
                "category": _score_category(score),
                "current_score": current_row["species_scores"][species_id]["score"],
                "best_datetime": best_row["datetime"],
                "best_score": best_row["species_scores"][species_id]["score"],
                "best_explanation": best_row["species_scores"][species_id]["explanation"],
                "seasonality_factor": best_row["species_scores"][species_id]["seasonality_factor"],
                "recommendation": (
                    f"Ventana mas favorable: "
                    f"{datetime.fromisoformat(best_row['datetime']).strftime('%d/%m %H:%M')}."
                ),
            }
        return summaries

    def _rescore_forecast(self, forecast: dict, fishing_context: FishingContext | None) -> dict:
        hourly_rows = forecast.get("hourly") or []
        for row in hourly_rows:
            conditions = _conditions_from_row(row)
            general_score = calculate_fishing_score(conditions, "general")
            row["fishing_score"] = general_score.score
            row["fishing_category"] = general_score.category
            row["explanation"] = general_score.explanation
            row["safety_alerts"] = general_score.safety_alerts
            row["confidence"] = general_score.confidence
            row["missing_fields"] = general_score.missing_fields
            row["factor_scores"] = general_score.factor_scores
            row["species_scores"] = {
                species["id"]: _serialize_score(calculate_fishing_score(conditions, species["id"], fishing_context))
                for species in list_species_profiles()
            }

        now_local = datetime.now(ZoneInfo(self.settings.canary_timezone))
        forecast["summary"] = self._summary(hourly_rows, now_local)
        fishing_context_data = serialize_fishing_context(fishing_context) if fishing_context else None
        forecast["fishing_context"] = fishing_context_data
        forecast.setdefault("meta", {})["fishing_context"] = fishing_context_data
        return forecast

    def _get_valid_cache(self, spot: FishingSpot) -> ForecastCache | None:
        now = utcnow()
        statement = (
            select(ForecastCache)
            .where(
                ForecastCache.spot_id == spot.id,
                ForecastCache.provider == self.provider_name,
                ForecastCache.expires_at > now,
            )
            .order_by(ForecastCache.created_at.desc())
            .limit(5)
        )
        return self._first_cache_matching_spot(statement, spot)

    def _get_latest_cache(self, spot: FishingSpot) -> ForecastCache | None:
        statement = (
            select(ForecastCache)
            .where(ForecastCache.spot_id == spot.id)
            .order_by(ForecastCache.created_at.desc())
            .limit(5)
        )
        return self._first_cache_matching_spot(statement, spot)

    def _first_cache_matching_spot(self, statement, spot: FishingSpot) -> ForecastCache | None:  # noqa: ANN001
        for cache in self.db.scalars(statement):
            if self._cache_matches_spot(cache, spot):
                return cache
        return None

    def _cache_matches_spot(self, cache: ForecastCache, spot: FishingSpot) -> bool:
        cached_spot = (cache.raw_data or {}).get("spot") or {}
        cached_meta = (cache.raw_data or {}).get("meta") or {}
        try:
            cached_latitude = float(cached_spot.get("latitude"))
            cached_longitude = float(cached_spot.get("longitude"))
        except (TypeError, ValueError):
            return False
        cached_days = cached_meta.get("forecast_days")
        if cached_days is not None:
            try:
                if int(cached_days) != int(self.settings.forecast_days):
                    return False
            except (TypeError, ValueError):
                return False
        return (
            abs(cached_latitude - float(spot.latitude)) < 0.000001
            and abs(cached_longitude - float(spot.longitude)) < 0.000001
        )

    def _store_cache(self, spot_id: int, forecast: dict) -> None:
        now = utcnow()
        cache = ForecastCache(
            spot_id=spot_id,
            provider=self.provider_name,
            forecast_datetime=now,
            raw_data=forecast,
            created_at=now,
            expires_at=now + timedelta(minutes=self.settings.forecast_cache_ttl_minutes),
        )
        self.db.add(cache)
        self.db.flush()
        self._prune_cache_rows(spot_id, keep_cache_id=cache.id)
        self.db.commit()

    def _prune_cache_rows(self, spot_id: int, keep_cache_id: int) -> None:
        statement = select(ForecastCache).where(
            ForecastCache.spot_id == spot_id,
            ForecastCache.provider == self.provider_name,
            ForecastCache.id != keep_cache_id,
        )
        for old_cache in self.db.scalars(statement):
            self.db.delete(old_cache)


def _merge_weather_payloads(successes: list[tuple[str, dict]]) -> dict:
    provider_names = [provider_name for provider_name, _ in successes]
    base = deepcopy(successes[0][1])
    base_hourly = base.get("hourly") or {}
    base_times: list[str] = base_hourly.get("time") or []
    provider_indexes = [
        (provider_name, payload, _time_index((payload.get("hourly") or {}).get("time") or []))
        for provider_name, payload in successes
    ]

    for field, digits in WEATHER_AVERAGE_FIELDS.items():
        base_hourly[field] = [
            _rounded_average(_values_for_time(provider_indexes, time_value, field), digits)
            for time_value in base_times
        ]

    for field in WEATHER_DIRECTION_FIELDS:
        base_hourly[field] = [
            _average_direction(_values_for_time(provider_indexes, time_value, field))
            for time_value in base_times
        ]

    base["hourly"] = base_hourly
    base["_arcafish_weather_meta"] = {
        "provider": "weather-ensemble",
        "providers": provider_names,
        "ensemble": True,
    }
    return base


def _time_index(times: list[str]) -> dict[str, int]:
    return {str(time_value): index for index, time_value in enumerate(times)}


def _values_for_time(provider_indexes: list[tuple[str, dict, dict[str, int]]], time_value: str, field: str) -> list[float]:
    values = []
    for _, payload, index_by_time in provider_indexes:
        index = index_by_time.get(time_value)
        if index is None:
            continue
        values_for_field = (payload.get("hourly") or {}).get(field) or []
        if index >= len(values_for_field):
            continue
        value = _number_or_none(values_for_field[index])
        if value is not None:
            values.append(value)
    return values


def _rounded_average(values: list[float], digits: int) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), digits)


def _average_direction(values: list[float]) -> int | None:
    if not values:
        return None
    x = sum(cos(value * pi / 180) for value in values) / len(values)
    y = sum(sin(value * pi / 180) for value in values) / len(values)
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return None
    return int(round((atan2(y, x) * 180 / pi + 360) % 360))


def _parse_local_datetime(value: str, tz: ZoneInfo) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _row_datetime(row: dict) -> datetime:
    return datetime.fromisoformat(row["datetime"])


def _conditions_from_row(row: dict) -> FishingConditions:
    return FishingConditions(
        datetime=datetime.fromisoformat(row["datetime"]),
        wind_speed_ms=_number_or_none(row.get("wind_speed_ms")),
        wind_gust_ms=_number_or_none(row.get("wind_gust_ms")),
        wind_direction_deg=_number_or_none(row.get("wind_direction_deg")),
        temperature_c=_number_or_none(row.get("temperature_c")),
        sea_surface_temperature_c=_number_or_none(row.get("sea_surface_temperature_c")),
        precipitation_mm=_number_or_none(row.get("precipitation_mm")),
        precipitation_probability=_number_or_none(row.get("precipitation_probability")),
        pressure_hpa=_number_or_none(row.get("pressure_hpa")),
        pressure_trend_hpa=_number_or_none(row.get("pressure_trend_hpa")),
        cloud_cover_percent=_number_or_none(row.get("cloud_cover_percent")),
        wave_height_m=_number_or_none(row.get("wave_height_m")),
        wave_period_s=_number_or_none(row.get("wave_period_s")),
        wave_direction_deg=_number_or_none(row.get("wave_direction_deg")),
        tide_state=None if row.get("tide_state") == "sin datos" else row.get("tide_state"),
        tide_height_m=_number_or_none(row.get("tide_height_m")),
        moon_phase=row.get("moon_phase"),
        sunrise=_datetime_or_none(row.get("sunrise")),
        sunset=_datetime_or_none(row.get("sunset")),
        is_day=None,
        weather_description=row.get("weather_description"),
    )


def _datetime_or_none(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _rows_for_next_24h(hourly_rows: list[dict], now_local: datetime) -> list[dict]:
    rows = [
        row
        for row in hourly_rows
        if now_local <= _row_datetime(row) < now_local + timedelta(hours=24)
    ]
    return rows or hourly_rows[:24]


def _current_or_first_row(hourly_rows: list[dict], now_local: datetime) -> dict:
    for row in hourly_rows:
        if _row_datetime(row) >= now_local:
            return row
    return hourly_rows[0]


def _summary_weights(length: int) -> list[float]:
    return [max(0.25, 1.0 - (index * 0.03)) for index in range(length)]


def _series_value(series: dict, key: str, index: int | None) -> float | None:
    if index is None:
        return None
    values = series.get(key) or []
    if index < 0 or index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _number_or_none(value: float | int | str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, digits: int) -> float | int | None:
    if value is None:
        return None
    rounded = round(value, digits)
    if digits == 0:
        return int(rounded)
    return rounded


def weather_code_description(code: float | None) -> str:
    if code is None:
        return "Sin datos"
    descriptions = {
        0: "Despejado",
        1: "Mayormente despejado",
        2: "Parcialmente nuboso",
        3: "Cubierto",
        45: "Niebla",
        48: "Niebla con escarcha",
        51: "Llovizna debil",
        53: "Llovizna",
        55: "Llovizna intensa",
        61: "Lluvia debil",
        63: "Lluvia",
        65: "Lluvia intensa",
        80: "Chubascos debiles",
        81: "Chubascos",
        82: "Chubascos fuertes",
        95: "Tormenta",
        96: "Tormenta con granizo",
        99: "Tormenta fuerte",
    }
    return descriptions.get(int(code), "Variable")


def _serialize_score(score) -> dict:  # noqa: ANN001
    return {
        "species_id": score.species_id,
        "species_name": score.species_name,
        "score": score.score,
        "base_score": score.base_score,
        "category": score.category,
        "explanation": score.explanation,
        "safety_alerts": score.safety_alerts,
        "confidence": score.confidence,
        "missing_fields": score.missing_fields,
        "factor_scores": score.factor_scores,
        "seasonality_factor": score.seasonality_factor,
        "method_factor": score.method_factor,
        "distance_factor": score.distance_factor,
        "target_zone_factor": score.target_zone_factor,
        "spot_factor": score.spot_factor,
    }


def _score_category(score: int) -> str:
    if score <= 39:
        return "Mala"
    if score <= 59:
        return "Regular"
    if score <= 79:
        return "Buena"
    return "Muy buena"


def _weighted_rows(rows: list[dict], key: str, weights: list[float]) -> int:
    total_weight = sum(weights) or 1.0
    weighted = sum(row[key] * weight for row, weight in zip(rows, weights, strict=False))
    return int(round(weighted / total_weight))


def _weighted_species_rows(rows: list[dict], species_id: str, weights: list[float]) -> int:
    total_weight = sum(weights) or 1.0
    weighted = sum(
        row["species_scores"][species_id]["score"] * weight
        for row, weight in zip(rows, weights, strict=False)
    )
    return int(round(weighted / total_weight))
