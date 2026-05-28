from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings, get_settings


class MetNoWeatherProvider:
    provider_name = "met-no-locationforecast"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def fetch(self, latitude: float, longitude: float, days: int) -> dict:
        params = {
            "lat": round(latitude, 4),
            "lon": round(longitude, 4),
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": self.settings.metno_user_agent,
        }
        async with httpx.AsyncClient(
            timeout=self.settings.http_timeout_seconds,
            verify=self.settings.http_verify_ssl,
            headers=headers,
        ) as client:
            response = await client.get(self.settings.metno_weather_url, params=params)
            response.raise_for_status()
            payload = response.json()
        return self._to_open_meteo_shape(payload, days)

    def _to_open_meteo_shape(self, payload: dict, days: int) -> dict:
        tz = ZoneInfo(self.settings.canary_timezone)
        end_local = datetime.now(tz) + timedelta(days=days)
        hourly = {
            "time": [],
            "temperature_2m": [],
            "precipitation": [],
            "precipitation_probability": [],
            "pressure_msl": [],
            "cloud_cover": [],
            "weather_code": [],
            "wind_speed_10m": [],
            "wind_direction_10m": [],
            "wind_gusts_10m": [],
            "is_day": [],
        }

        for item in (payload.get("properties") or {}).get("timeseries") or []:
            moment = _parse_metno_time(item.get("time")).astimezone(tz)
            if moment > end_local:
                continue

            data = item.get("data") or {}
            instant = ((data.get("instant") or {}).get("details") or {})
            next_hour = data.get("next_1_hours") or {}
            next_hour_details = next_hour.get("details") or {}
            symbol_code = ((next_hour.get("summary") or {}).get("symbol_code") or "").lower()

            hourly["time"].append(moment.strftime("%Y-%m-%dT%H:%M"))
            hourly["temperature_2m"].append(_number_or_none(instant.get("air_temperature")))
            hourly["precipitation"].append(_number_or_none(next_hour_details.get("precipitation_amount")))
            hourly["precipitation_probability"].append(
                _number_or_none(next_hour_details.get("probability_of_precipitation"))
            )
            hourly["pressure_msl"].append(_number_or_none(instant.get("air_pressure_at_sea_level")))
            hourly["cloud_cover"].append(_number_or_none(instant.get("cloud_area_fraction")))
            hourly["weather_code"].append(_symbol_to_weather_code(symbol_code))
            hourly["wind_speed_10m"].append(_number_or_none(instant.get("wind_speed")))
            hourly["wind_direction_10m"].append(_number_or_none(instant.get("wind_from_direction")))
            hourly["wind_gusts_10m"].append(_number_or_none(instant.get("wind_speed_of_gust")))
            hourly["is_day"].append(_is_day_from_symbol(symbol_code))

        return {
            "latitude": payload.get("geometry", {}).get("coordinates", [None, None])[1],
            "longitude": payload.get("geometry", {}).get("coordinates", [None, None])[0],
            "hourly": hourly,
            "meta": {
                "provider": self.provider_name,
                "updated_at": (payload.get("properties") or {}).get("meta", {}).get("updated_at"),
            },
        }


def _parse_metno_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _number_or_none(value: float | int | str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_day_from_symbol(symbol_code: str) -> int | None:
    if symbol_code.endswith("_day"):
        return 1
    if symbol_code.endswith("_night"):
        return 0
    return None


def _symbol_to_weather_code(symbol_code: str) -> int | None:
    if not symbol_code:
        return None
    base = symbol_code.split("_", 1)[0]
    if base == "clearsky":
        return 0
    if base == "fair":
        return 1
    if base == "partlycloudy":
        return 2
    if base == "cloudy":
        return 3
    if "fog" in base:
        return 45
    if "thunder" in base:
        return 95
    if "heavyrain" in base:
        return 65
    if "lightrain" in base:
        return 61
    if "rainshowers" in base:
        return 80
    if "rain" in base:
        return 63
    if "heavysnow" in base:
        return 75
    if "lightsnow" in base:
        return 71
    if "snow" in base:
        return 73
    if "sleet" in base:
        return 69
    return None
