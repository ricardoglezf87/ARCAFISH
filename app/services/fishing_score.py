from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import exp


WIND_DANGEROUS_MS = 14.0
GUST_DANGEROUS_MS = 18.0
WAVE_DANGEROUS_M = 2.8
WAVE_CAUTION_M = 2.1
RAIN_HEAVY_MM = 4.0


@dataclass(frozen=True)
class FishingConditions:
    datetime: datetime
    wind_speed_ms: float | None = None
    wind_gust_ms: float | None = None
    wind_direction_deg: float | None = None
    temperature_c: float | None = None
    sea_surface_temperature_c: float | None = None
    precipitation_mm: float | None = None
    precipitation_probability: float | None = None
    pressure_hpa: float | None = None
    pressure_trend_hpa: float | None = None
    cloud_cover_percent: float | None = None
    wave_height_m: float | None = None
    wave_period_s: float | None = None
    wave_direction_deg: float | None = None
    tide_state: str | None = None
    tide_height_m: float | None = None
    moon_phase: str | None = None
    sunrise: datetime | None = None
    sunset: datetime | None = None
    is_day: bool | None = None
    weather_description: str | None = None
    missing_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SpeciesProfile:
    id: str
    name: str
    description: str
    weights: dict[str, float]
    wind_range: tuple[float, float]
    wave_range: tuple[float, float]
    water_temp_range: tuple[float, float] | None
    light_preferences: dict[str, float]
    tide_preferences: dict[str, float]
    seasonality_by_month: dict[int, float]
    cloud_mode: str = "moderate"
    notes: str = ""


@dataclass(frozen=True)
class FishingScoreResult:
    species_id: str
    species_name: str
    score: int
    category: str
    explanation: str
    safety_alerts: list[str]
    confidence: str
    missing_fields: list[str]
    factor_scores: dict[str, float]
    seasonality_factor: float


GENERAL_WEIGHTS = {
    "wind": 0.12,
    "gust": 0.08,
    "wave_height": 0.14,
    "wave_period": 0.07,
    "rain": 0.05,
    "pressure": 0.08,
    "pressure_trend": 0.08,
    "tide": 0.12,
    "light": 0.11,
    "cloud": 0.06,
    "water_temp": 0.05,
    "air_temp": 0.02,
    "moon": 0.02,
}


SPECIES_PROFILES: dict[str, SpeciesProfile] = {
    "general": SpeciesProfile(
        id="general",
        name="General costa",
        description="Indice base para pesca desde costa sin distinguir especie.",
        weights=GENERAL_WEIGHTS,
        wind_range=(2.0, 6.5),
        wave_range=(0.5, 1.4),
        water_temp_range=(19.0, 24.0),
        light_preferences={"dawn": 1.0, "dusk": 1.0, "night": 0.65, "day": 0.55, "midday": 0.42},
        tide_preferences={"subiendo": 1.0, "bajando": 0.8, "pleamar": 0.55, "bajamar": 0.45, "estable": 0.35},
        seasonality_by_month={month: 1.0 for month in range(1, 13)},
        cloud_mode="moderate",
        notes="Promedia mejor las proximas 24 horas que una sola ventana ideal.",
    ),
    "dorado": SpeciesProfile(
        id="dorado",
        name="Dorado / Lampuga",
        description="Pelagico diurno de aguas calidas y mar relativamente ordenado.",
        weights={**GENERAL_WEIGHTS, "light": 0.16, "water_temp": 0.13, "wave_height": 0.10, "cloud": 0.04},
        wind_range=(2.5, 7.0),
        wave_range=(0.4, 1.3),
        water_temp_range=(24.0, 29.5),
        light_preferences={"dawn": 0.85, "dusk": 0.85, "night": 0.1, "day": 1.0, "midday": 0.92},
        tide_preferences={"subiendo": 0.9, "bajando": 0.7, "pleamar": 0.55, "bajamar": 0.4, "estable": 0.45},
        seasonality_by_month={1: 0.0, 2: 0.0, 3: 0.1, 4: 0.3, 5: 0.6, 6: 0.8, 7: 1.0, 8: 1.0, 9: 1.0, 10: 0.7, 11: 0.4, 12: 0.1},
        cloud_mode="clear_day",
    ),
    "medregal": SpeciesProfile(
        id="medregal",
        name="Medregal / Seriola",
        description="Depredador activo con mar moderado, corriente y buena visibilidad.",
        weights={**GENERAL_WEIGHTS, "water_temp": 0.10, "wave_period": 0.09, "tide": 0.14},
        wind_range=(2.0, 7.0),
        wave_range=(0.6, 1.7),
        water_temp_range=(20.0, 25.5),
        light_preferences={"dawn": 0.95, "dusk": 0.95, "night": 0.3, "day": 0.88, "midday": 0.75},
        tide_preferences={"subiendo": 1.0, "bajando": 0.85, "pleamar": 0.6, "bajamar": 0.45, "estable": 0.4},
        seasonality_by_month={1: 0.5, 2: 0.6, 3: 0.7, 4: 0.8, 5: 0.9, 6: 1.0, 7: 1.0, 8: 0.9, 9: 0.7, 10: 0.6, 11: 0.5, 12: 0.5},
        cloud_mode="moderate",
    ),
    "bicuda": SpeciesProfile(
        id="bicuda",
        name="Bicuda / Aguja / Sierra",
        description="Pelagicos de superficie muy ligados a amanecer, atardecer y corriente entrante.",
        weights={**GENERAL_WEIGHTS, "light": 0.17, "tide": 0.15, "wave_height": 0.11},
        wind_range=(2.0, 6.0),
        wave_range=(0.4, 1.2),
        water_temp_range=(20.0, 25.5),
        light_preferences={"dawn": 1.0, "dusk": 1.0, "night": 0.25, "day": 0.7, "midday": 0.4},
        tide_preferences={"subiendo": 1.0, "bajando": 0.75, "pleamar": 0.55, "bajamar": 0.45, "estable": 0.35},
        seasonality_by_month={1: 1.0, 2: 1.0, 3: 0.8, 4: 0.5, 5: 0.3, 6: 0.2, 7: 0.2, 8: 0.3, 9: 0.5, 10: 0.8, 11: 1.0, 12: 1.0},
        cloud_mode="moderate",
    ),
    "bocinegro_sama": SpeciesProfile(
        id="bocinegro_sama",
        name="Bocinegro / Sama",
        description="Fondo-costero mas activo con luz baja, noche y mar tranquilo.",
        weights={**GENERAL_WEIGHTS, "light": 0.18, "wave_height": 0.16, "cloud": 0.07},
        wind_range=(1.0, 5.5),
        wave_range=(0.2, 0.9),
        water_temp_range=(18.0, 23.5),
        light_preferences={"dawn": 0.85, "dusk": 1.0, "night": 1.0, "day": 0.35, "midday": 0.15},
        tide_preferences={"subiendo": 0.8, "bajando": 0.75, "pleamar": 0.65, "bajamar": 0.55, "estable": 0.4},
        seasonality_by_month={1: 0.8, 2: 0.8, 3: 0.6, 4: 0.4, 5: 0.2, 6: 0.1, 7: 0.0, 8: 0.0, 9: 0.1, 10: 0.3, 11: 0.6, 12: 0.8},
        cloud_mode="low_light",
    ),
    "vieja_pejeverde": SpeciesProfile(
        id="vieja_pejeverde",
        name="Vieja / Peje verde",
        description="Costero de roca, con mejor respuesta en mar estable y horas medias o luz suave.",
        weights={**GENERAL_WEIGHTS, "wave_height": 0.18, "light": 0.11, "wind": 0.10},
        wind_range=(1.0, 5.0),
        wave_range=(0.2, 0.8),
        water_temp_range=(18.0, 24.0),
        light_preferences={"dawn": 0.7, "dusk": 0.85, "night": 0.45, "day": 0.82, "midday": 0.88},
        tide_preferences={"subiendo": 0.75, "bajando": 0.7, "pleamar": 0.6, "bajamar": 0.55, "estable": 0.55},
        seasonality_by_month={1: 0.1, 2: 0.1, 3: 0.2, 4: 0.4, 5: 0.6, 6: 0.8, 7: 0.9, 8: 1.0, 9: 1.0, 10: 0.8, 11: 0.4, 12: 0.2},
        cloud_mode="moderate",
    ),
    "sargo_chopa_roncador": SpeciesProfile(
        id="sargo_chopa_roncador",
        name="Sargo / Chopa / Roncador",
        description="Muy agradecidos a luz baja, algo de corriente y agua razonablemente limpia.",
        weights={**GENERAL_WEIGHTS, "light": 0.16, "tide": 0.14, "cloud": 0.07},
        wind_range=(1.5, 6.0),
        wave_range=(0.4, 1.3),
        water_temp_range=(18.0, 23.5),
        light_preferences={"dawn": 1.0, "dusk": 1.0, "night": 0.7, "day": 0.45, "midday": 0.25},
        tide_preferences={"subiendo": 0.95, "bajando": 0.8, "pleamar": 0.6, "bajamar": 0.5, "estable": 0.35},
        seasonality_by_month={1: 1.0, 2: 1.0, 3: 0.9, 4: 0.7, 5: 0.4, 6: 0.2, 7: 0.1, 8: 0.1, 9: 0.2, 10: 0.5, 11: 0.8, 12: 1.0},
        cloud_mode="low_light",
    ),
    "jurel_palometa_boga": SpeciesProfile(
        id="jurel_palometa_boga",
        name="Jurel / Palometa / Boga",
        description="Pelagicos pequenos de dia con oxigenacion, corriente y agua templada.",
        weights={**GENERAL_WEIGHTS, "wind": 0.13, "tide": 0.13, "water_temp": 0.08},
        wind_range=(2.0, 7.0),
        wave_range=(0.5, 1.5),
        water_temp_range=(19.0, 24.5),
        light_preferences={"dawn": 0.9, "dusk": 0.9, "night": 0.3, "day": 0.9, "midday": 0.7},
        tide_preferences={"subiendo": 0.95, "bajando": 0.8, "pleamar": 0.55, "bajamar": 0.45, "estable": 0.4},
        seasonality_by_month={1: 0.9, 2: 0.9, 3: 0.8, 4: 0.6, 5: 0.4, 6: 0.2, 7: 0.1, 8: 0.1, 9: 0.3, 10: 0.6, 11: 0.8, 12: 0.9},
        cloud_mode="moderate",
    ),
    "burro_fula": SpeciesProfile(
        id="burro_fula",
        name="Burro listado / Fula",
        description="Fondos y estructuras tranquilas, mas estable que explosivo.",
        weights={**GENERAL_WEIGHTS, "wave_height": 0.18, "wind": 0.13, "light": 0.09},
        wind_range=(0.8, 4.5),
        wave_range=(0.2, 0.8),
        water_temp_range=(18.0, 24.0),
        light_preferences={"dawn": 0.8, "dusk": 0.8, "night": 0.4, "day": 0.85, "midday": 0.75},
        tide_preferences={"subiendo": 0.75, "bajando": 0.7, "pleamar": 0.55, "bajamar": 0.5, "estable": 0.55},
        seasonality_by_month={1: 0.1, 2: 0.1, 3: 0.2, 4: 0.4, 5: 0.7, 6: 0.9, 7: 1.0, 8: 1.0, 9: 0.8, 10: 0.5, 11: 0.2, 12: 0.1},
        cloud_mode="moderate",
    ),
    "catalufa": SpeciesProfile(
        id="catalufa",
        name="Catalufa",
        description="Especie claramente nocturna; el dia le resta muchos enteros.",
        weights={**GENERAL_WEIGHTS, "light": 0.24, "moon": 0.05, "wave_height": 0.15},
        wind_range=(0.8, 4.5),
        wave_range=(0.2, 0.9),
        water_temp_range=(18.0, 24.0),
        light_preferences={"dawn": 0.5, "dusk": 0.9, "night": 1.0, "day": 0.08, "midday": 0.03},
        tide_preferences={"subiendo": 0.8, "bajando": 0.75, "pleamar": 0.7, "bajamar": 0.5, "estable": 0.4},
        seasonality_by_month={1: 0.3, 2: 0.3, 3: 0.4, 4: 0.6, 5: 0.8, 6: 0.9, 7: 1.0, 8: 1.0, 9: 0.7, 10: 0.5, 11: 0.3, 12: 0.3},
        cloud_mode="low_light",
    ),
    "pulpo": SpeciesProfile(
        id="pulpo",
        name="Pulpo",
        description="Nocturno, de roca y mar calmado. Penaliza bastante el sol duro.",
        weights={**GENERAL_WEIGHTS, "light": 0.24, "wave_height": 0.18, "tide": 0.14, "cloud": 0.06},
        wind_range=(0.5, 4.0),
        wave_range=(0.1, 0.7),
        water_temp_range=(17.0, 23.5),
        light_preferences={"dawn": 0.75, "dusk": 1.0, "night": 1.0, "day": 0.2, "midday": 0.05},
        tide_preferences={"subiendo": 0.65, "bajando": 0.95, "pleamar": 0.7, "bajamar": 0.45, "estable": 0.4},
        seasonality_by_month={1: 0.2, 2: 0.2, 3: 0.3, 4: 0.5, 5: 0.7, 6: 0.8, 7: 0.9, 8: 1.0, 9: 1.0, 10: 0.9, 11: 0.6, 12: 0.4},
        cloud_mode="low_light",
    ),
}


FACTOR_LABELS = {
    "wind": "viento",
    "gust": "rachas",
    "wave_height": "oleaje",
    "wave_period": "periodo de ola",
    "rain": "lluvia",
    "pressure": "presion",
    "pressure_trend": "tendencia de presion",
    "tide": "marea",
    "light": "luz",
    "cloud": "nubosidad",
    "water_temp": "temperatura del agua",
    "air_temp": "temperatura ambiente",
    "moon": "fase lunar",
}


def calculate_fishing_score(
    conditions: FishingConditions,
    species_id: str = "general",
) -> FishingScoreResult:
    profile = SPECIES_PROFILES.get(species_id, SPECIES_PROFILES["general"])
    missing_fields = list(conditions.missing_fields)
    factor_scores = _compute_factor_scores(conditions, profile, missing_fields)
    safety_alerts, safety_multiplier = _safety_assessment(conditions)
    confidence_multiplier = _confidence_multiplier(missing_fields)
    weighted_score = _weighted_average(factor_scores, profile.weights)
    base_score = 100 / (1 + exp(-7.5 * (weighted_score - 0.72)))
    seasonality_factor = _seasonality_factor(conditions.datetime.month, profile)
    final_score = int(
        round(max(0, min(100, base_score * seasonality_factor * safety_multiplier * confidence_multiplier)))
    )

    if safety_multiplier <= 0.45:
        final_score = min(final_score, 39)
    elif safety_multiplier < 1:
        final_score = min(final_score, 59)

    category = score_category(final_score)
    confidence = _confidence_label(missing_fields)
    explanation = _build_explanation(
        factor_scores=factor_scores,
        profile=profile,
        month=conditions.datetime.month,
        safety_alerts=safety_alerts,
        confidence=confidence,
    )

    return FishingScoreResult(
        species_id=profile.id,
        species_name=profile.name,
        score=final_score,
        category=category,
        explanation=explanation,
        safety_alerts=safety_alerts,
        confidence=confidence,
        missing_fields=sorted(set(missing_fields)),
        factor_scores={key: round(value, 3) for key, value in factor_scores.items()},
        seasonality_factor=round(seasonality_factor, 2),
    )


def score_category(score: int) -> str:
    if score <= 39:
        return "Mala"
    if score <= 59:
        return "Regular"
    if score <= 79:
        return "Buena"
    return "Muy buena"


def list_species_profiles() -> list[dict]:
    ordered_ids = [species_id for species_id in SPECIES_PROFILES if species_id != "general"]
    return [
        {
            "id": species_id,
            "name": SPECIES_PROFILES[species_id].name,
            "description": SPECIES_PROFILES[species_id].description,
            "notes": SPECIES_PROFILES[species_id].notes,
            "seasonality_by_month": SPECIES_PROFILES[species_id].seasonality_by_month,
        }
        for species_id in ordered_ids
    ]


def _compute_factor_scores(
    conditions: FishingConditions,
    profile: SpeciesProfile,
    missing_fields: list[str],
) -> dict[str, float]:
    return {
        "wind": _factor_range(conditions.wind_speed_ms, *profile.wind_range, 0.5, 16.0, missing_fields, "wind_speed_ms"),
        "gust": _factor_inverse(conditions.wind_gust_ms, 8.5, 18.0, missing_fields, "wind_gust_ms"),
        "wave_height": _factor_range(conditions.wave_height_m, *profile.wave_range, 0.1, 3.2, missing_fields, "wave_height_m"),
        "wave_period": _wave_period_factor(conditions, missing_fields),
        "rain": _rain_factor(conditions.precipitation_mm, missing_fields),
        "pressure": _pressure_factor(conditions.pressure_hpa, missing_fields),
        "pressure_trend": _pressure_trend_factor(conditions.pressure_trend_hpa, missing_fields),
        "tide": _tide_factor(conditions.tide_state, profile, missing_fields),
        "light": _light_factor(conditions, profile, missing_fields),
        "cloud": _cloud_factor(conditions.cloud_cover_percent, profile, missing_fields),
        "water_temp": _water_temp_factor(conditions.sea_surface_temperature_c, profile, missing_fields),
        "air_temp": _air_temp_factor(conditions.temperature_c, missing_fields),
        "moon": _moon_factor(conditions.moon_phase),
    }


def _weighted_average(factor_scores: dict[str, float], weights: dict[str, float]) -> float:
    total_weight = sum(weights.values()) or 1.0
    return sum(factor_scores[key] * weight for key, weight in weights.items()) / total_weight


def _factor_range(
    value: float | None,
    ideal_low: float,
    ideal_high: float,
    hard_low: float,
    hard_high: float,
    missing_fields: list[str],
    field_name: str,
) -> float:
    if value is None:
        missing_fields.append(field_name)
        return 0.5
    return _trapezoid(float(value), hard_low, ideal_low, ideal_high, hard_high)


def _factor_inverse(value: float | None, ideal_max: float, hard_max: float, missing_fields: list[str], field_name: str) -> float:
    if value is None:
        missing_fields.append(field_name)
        return 0.5
    if value <= ideal_max:
        return 1.0
    if value >= hard_max:
        return 0.0
    return 1.0 - ((value - ideal_max) / (hard_max - ideal_max))


def _wave_period_factor(conditions: FishingConditions, missing_fields: list[str]) -> float:
    period = conditions.wave_period_s
    if period is None:
        missing_fields.append("wave_period_s")
        return 0.5
    factor = _trapezoid(float(period), 3.0, 6.0, 10.0, 14.0)
    if conditions.wave_height_m is not None and conditions.wave_height_m >= 1.8 and period >= 12:
        factor *= 0.7
    return factor


def _rain_factor(rain_mm: float | None, missing_fields: list[str]) -> float:
    if rain_mm is None:
        missing_fields.append("precipitation_mm")
        return 0.5
    if rain_mm <= 0:
        return 1.0
    if rain_mm <= 0.6:
        return 0.85
    if rain_mm <= 1.5:
        return 0.65
    if rain_mm <= RAIN_HEAVY_MM:
        return 0.35
    return 0.08


def _pressure_factor(pressure_hpa: float | None, missing_fields: list[str]) -> float:
    if pressure_hpa is None:
        missing_fields.append("pressure_hpa")
        return 0.5
    return _trapezoid(float(pressure_hpa), 1004.0, 1011.0, 1020.0, 1028.0)


def _pressure_trend_factor(trend_hpa: float | None, missing_fields: list[str]) -> float:
    if trend_hpa is None:
        missing_fields.append("pressure_trend_hpa")
        return 0.5
    if -1.0 <= trend_hpa <= 0.8:
        return 1.0
    if -2.0 <= trend_hpa < -1.0:
        return 0.78
    if 0.8 < trend_hpa <= 2.0:
        return 0.72
    if trend_hpa < -3.0:
        return 0.22
    return 0.45


def _tide_factor(tide_state: str | None, profile: SpeciesProfile, missing_fields: list[str]) -> float:
    if not tide_state:
        missing_fields.append("tide_state")
        return 0.5
    normalized = tide_state.lower()
    return profile.tide_preferences.get(normalized, 0.45)


def _light_factor(conditions: FishingConditions, profile: SpeciesProfile, missing_fields: list[str]) -> float:
    phase = _time_phase(conditions, missing_fields)
    return profile.light_preferences.get(phase, 0.5)


def _cloud_factor(cloud_cover: float | None, profile: SpeciesProfile, missing_fields: list[str]) -> float:
    if cloud_cover is None:
        missing_fields.append("cloud_cover_percent")
        return 0.5
    cloud = float(cloud_cover)
    if profile.cloud_mode == "clear_day":
        if cloud <= 25:
            return 1.0
        if cloud <= 55:
            return 0.8
        if cloud <= 80:
            return 0.55
        return 0.35
    if profile.cloud_mode == "low_light":
        if cloud <= 20:
            return 0.45
        if cloud <= 50:
            return 0.72
        if cloud <= 85:
            return 0.95
        return 0.82
    if cloud <= 15:
        return 0.55
    if cloud <= 45:
        return 0.82
    if cloud <= 75:
        return 1.0
    return 0.78


def _water_temp_factor(value: float | None, profile: SpeciesProfile, missing_fields: list[str]) -> float:
    if value is None:
        missing_fields.append("sea_surface_temperature_c")
        return 0.5
    if profile.water_temp_range is None:
        return 0.5
    ideal_low, ideal_high = profile.water_temp_range
    return _trapezoid(float(value), ideal_low - 4.0, ideal_low, ideal_high, ideal_high + 4.0)


def _air_temp_factor(value: float | None, missing_fields: list[str]) -> float:
    if value is None:
        missing_fields.append("temperature_c")
        return 0.5
    return _trapezoid(float(value), 12.0, 18.0, 24.0, 31.0)


def _moon_factor(phase: str | None) -> float:
    normalized = (phase or "").lower()
    if normalized in {"nueva", "llena"}:
        return 0.72
    if normalized in {"creciente", "menguante", "cuarto creciente", "cuarto menguante"}:
        return 0.62
    if normalized:
        return 0.56
    return 0.5


def _safety_assessment(conditions: FishingConditions) -> tuple[list[str], float]:
    alerts: list[str] = []
    multiplier = 1.0

    if conditions.wave_height_m is not None:
        if conditions.wave_height_m >= WAVE_DANGEROUS_M:
            alerts.append("Oleaje muy alto para pesca desde costa.")
            multiplier = min(multiplier, 0.35)
        elif conditions.wave_height_m >= WAVE_CAUTION_M:
            alerts.append("Oleaje alto; evita zonas expuestas.")
            multiplier = min(multiplier, 0.72)

    if conditions.wind_speed_ms is not None:
        if conditions.wind_speed_ms >= WIND_DANGEROUS_MS:
            alerts.append("Viento fuerte para espigones y roca.")
            multiplier = min(multiplier, 0.4)
        elif conditions.wind_speed_ms >= 10.5:
            alerts.append("Viento exigente para pesca comoda.")
            multiplier = min(multiplier, 0.8)

    if conditions.wind_gust_ms is not None:
        if conditions.wind_gust_ms >= GUST_DANGEROUS_MS:
            alerts.append("Rachas peligrosas en costa abierta.")
            multiplier = min(multiplier, 0.35)
        elif conditions.wind_gust_ms >= 14.5:
            alerts.append("Rachas intensas; extrema la precaucion.")
            multiplier = min(multiplier, 0.75)

    if conditions.precipitation_mm is not None and conditions.precipitation_mm >= RAIN_HEAVY_MM:
        alerts.append("Lluvia intensa prevista.")
        multiplier = min(multiplier, 0.78)

    return list(dict.fromkeys(alerts)), multiplier


def _confidence_multiplier(missing_fields: Iterable[str]) -> float:
    unique_missing = len(set(missing_fields))
    return max(0.82, 1.0 - (unique_missing * 0.025))


def _confidence_label(missing_fields: Iterable[str]) -> str:
    unique_missing = len(set(missing_fields))
    if unique_missing <= 2:
        return "alta"
    if unique_missing <= 5:
        return "media"
    return "baja"


def _build_explanation(
    factor_scores: dict[str, float],
    profile: SpeciesProfile,
    month: int,
    safety_alerts: list[str],
    confidence: str,
) -> str:
    weighted_deltas = [
        (factor_id, profile.weights.get(factor_id, 0.0) * (factor_value - 0.5))
        for factor_id, factor_value in factor_scores.items()
    ]
    positives = [item for item in weighted_deltas if item[1] > 0.02]
    negatives = [item for item in weighted_deltas if item[1] < -0.02]
    positives.sort(key=lambda item: item[1], reverse=True)
    negatives.sort(key=lambda item: item[1])

    parts: list[str] = []
    if positives:
        parts.append("Suman " + ", ".join(FACTOR_LABELS[item[0]] for item in positives[:3]) + ".")
    else:
        parts.append("No aparecen apoyos claros en los factores principales.")

    if negatives:
        parts.append("Restan " + ", ".join(FACTOR_LABELS[item[0]] for item in negatives[:3]) + ".")

    if safety_alerts:
        parts.append("Alerta: " + safety_alerts[0])

    seasonality = _seasonality_factor(month, profile)
    if seasonality <= 0.35 and profile.id != "general":
        parts.append("Es mes flojo para esta especie.")
    elif seasonality >= 0.85 and profile.id != "general":
        parts.append("La estacionalidad acompana.")

    if confidence != "alta":
        parts.append(f"Confianza {confidence} por datos incompletos.")

    return " ".join(parts)


def _time_phase(conditions: FishingConditions, missing_fields: list[str]) -> str:
    if not conditions.sunrise or not conditions.sunset:
        missing_fields.extend(["sunrise", "sunset"])
        return "day" if conditions.is_day else "night"

    moment = conditions.datetime
    if _within(moment, conditions.sunrise, 90):
        return "dawn"
    if _within(moment, conditions.sunset, 105):
        return "dusk"
    if conditions.sunrise < moment < conditions.sunset:
        daylight = conditions.sunset - conditions.sunrise
        midday_start = conditions.sunrise + (daylight * 0.35)
        midday_end = conditions.sunrise + (daylight * 0.7)
        if midday_start <= moment <= midday_end:
            return "midday"
        return "day"
    return "night"


def _within(moment: datetime, target: datetime, minutes: int) -> bool:
    return abs(moment - target) <= timedelta(minutes=minutes)


def _trapezoid(value: float, hard_low: float, ideal_low: float, ideal_high: float, hard_high: float) -> float:
    if value <= hard_low or value >= hard_high:
        return 0.0
    if ideal_low <= value <= ideal_high:
        return 1.0
    if value < ideal_low:
        return (value - hard_low) / (ideal_low - hard_low)
    return 1.0 - ((value - ideal_high) / (hard_high - ideal_high))


def _seasonality_factor(month: int, profile: SpeciesProfile) -> float:
    return profile.seasonality_by_month.get(int(month), 0.5)
