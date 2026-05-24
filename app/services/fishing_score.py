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
class FishingContext:
    fishing_method: str
    casting_distance_m: float
    target_zone: str
    water_column: str
    spot_type: str | None = None
    shore_type: str | None = None
    spot_exposure: str | None = None
    water_depth_estimate_m: float | None = None


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
    base_score: int
    category: str
    explanation: str
    safety_alerts: list[str]
    confidence: str
    missing_fields: list[str]
    factor_scores: dict[str, float]
    seasonality_factor: float
    method_factor: float = 1.0
    distance_factor: float = 1.0
    target_zone_factor: float = 1.0
    spot_factor: float = 1.0


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


ALLOWED_FISHING_METHODS = {"float", "bottom", "spinning", "lure_trolling_like"}
ALLOWED_TARGET_ZONES = {"shoreline", "shore_break", "inner_reef", "outer_reef", "deep_cast"}
ALLOWED_WATER_COLUMNS = {"surface", "mid_water", "bottom"}

FISHING_METHOD_FACTORS = {
    "float": 0.9,
    "bottom": 1.0,
    "spinning": 1.0,
    "lure_trolling_like": 1.1,
}

FISHING_METHOD_LABELS = {
    "float": "Boya",
    "bottom": "Fondo",
    "spinning": "Spinning",
    "lure_trolling_like": "Senuelo con avance",
}

TARGET_ZONE_LABELS = {
    "shoreline": "orilla directa",
    "shore_break": "primera rompiente",
    "inner_reef": "arrecife interior",
    "outer_reef": "zona exterior",
    "deep_cast": "lance profundo",
}

SPECIES_DISTANCE_PROFILES: dict[str, list[dict[str, float]]] = {
    "sargo_chopa_roncador": [
        {"min": 0, "max": 20, "factor": 1.0},
        {"min": 20, "max": 40, "factor": 0.9},
        {"min": 40, "max": 70, "factor": 0.5},
        {"min": 70, "max": 999, "factor": 0.2},
    ],
    "vieja_pejeverde": [
        {"min": 0, "max": 30, "factor": 1.0},
        {"min": 30, "max": 50, "factor": 0.55},
        {"min": 50, "max": 999, "factor": 0.25},
    ],
    "pulpo": [
        {"min": 0, "max": 25, "factor": 1.0},
        {"min": 25, "max": 50, "factor": 0.45},
        {"min": 50, "max": 999, "factor": 0.15},
    ],
    "jurel_palometa_boga": [
        {"min": 0, "max": 20, "factor": 0.8},
        {"min": 20, "max": 60, "factor": 1.0},
        {"min": 60, "max": 90, "factor": 0.55},
        {"min": 90, "max": 999, "factor": 0.25},
    ],
    "catalufa": [
        {"min": 0, "max": 10, "factor": 0.55},
        {"min": 10, "max": 40, "factor": 1.0},
        {"min": 40, "max": 70, "factor": 0.45},
        {"min": 70, "max": 999, "factor": 0.2},
    ],
    "bicuda": [
        {"min": 0, "max": 20, "factor": 0.45},
        {"min": 20, "max": 80, "factor": 1.0},
        {"min": 80, "max": 120, "factor": 0.55},
        {"min": 120, "max": 999, "factor": 0.25},
    ],
    "bocinegro_sama": [
        {"min": 0, "max": 30, "factor": 0.1},
        {"min": 30, "max": 40, "factor": 0.45},
        {"min": 40, "max": 60, "factor": 0.75},
        {"min": 60, "max": 120, "factor": 1.0},
        {"min": 120, "max": 150, "factor": 0.8},
        {"min": 150, "max": 999, "factor": 0.5},
    ],
    "medregal": [
        {"min": 0, "max": 30, "factor": 0.15},
        {"min": 30, "max": 50, "factor": 0.55},
        {"min": 50, "max": 120, "factor": 1.0},
        {"min": 120, "max": 160, "factor": 0.7},
        {"min": 160, "max": 999, "factor": 0.4},
    ],
    "dorado": [
        {"min": 0, "max": 50, "factor": 0.1},
        {"min": 50, "max": 70, "factor": 0.45},
        {"min": 70, "max": 150, "factor": 1.0},
        {"min": 150, "max": 999, "factor": 0.8},
    ],
    "burro_fula": [
        {"min": 0, "max": 40, "factor": 0.85},
        {"min": 40, "max": 80, "factor": 0.55},
        {"min": 80, "max": 999, "factor": 0.25},
    ],
}

SPECIES_TARGET_ZONE_FACTORS: dict[str, dict[str, float]] = {
    "sargo_chopa_roncador": {"shoreline": 0.98, "shore_break": 1.05, "inner_reef": 0.95, "outer_reef": 0.82, "deep_cast": 0.75},
    "vieja_pejeverde": {"shoreline": 1.05, "shore_break": 1.02, "inner_reef": 0.88, "outer_reef": 0.78, "deep_cast": 0.7},
    "pulpo": {"shoreline": 1.05, "shore_break": 1.0, "inner_reef": 0.9, "outer_reef": 0.78, "deep_cast": 0.7},
    "jurel_palometa_boga": {"shoreline": 0.95, "shore_break": 1.0, "inner_reef": 1.05, "outer_reef": 0.9, "deep_cast": 0.78},
    "catalufa": {"shoreline": 0.86, "shore_break": 1.0, "inner_reef": 1.04, "outer_reef": 0.86, "deep_cast": 0.72},
    "bicuda": {"shoreline": 0.84, "shore_break": 0.9, "inner_reef": 1.05, "outer_reef": 1.02, "deep_cast": 0.82},
    "bocinegro_sama": {"shoreline": 0.85, "shore_break": 0.85, "inner_reef": 0.95, "outer_reef": 1.06, "deep_cast": 1.02},
    "medregal": {"shoreline": 0.85, "shore_break": 0.9, "inner_reef": 0.98, "outer_reef": 1.06, "deep_cast": 1.0},
    "dorado": {"shoreline": 0.82, "shore_break": 0.85, "inner_reef": 0.94, "outer_reef": 1.05, "deep_cast": 1.08},
    "burro_fula": {"shoreline": 1.02, "shore_break": 1.0, "inner_reef": 0.92, "outer_reef": 0.82, "deep_cast": 0.72},
}

ROCK_AND_REEF_SPECIES = {"sargo_chopa_roncador", "vieja_pejeverde", "pulpo", "catalufa", "burro_fula"}
LONG_CAST_SPECIES = {"bocinegro_sama", "medregal", "dorado", "bicuda"}


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
    fishing_context: FishingContext | None = None,
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

    weather_score = final_score
    method_factor, distance_factor, target_zone_factor, spot_factor = _context_factors(
        conditions,
        profile,
        fishing_context,
    )
    final_score = int(
        round(max(0, min(100, weather_score * method_factor * distance_factor * target_zone_factor * spot_factor)))
    )

    category = score_category(final_score)
    confidence = _confidence_label(missing_fields)
    explanation = _build_explanation(
        factor_scores=factor_scores,
        profile=profile,
        month=conditions.datetime.month,
        safety_alerts=safety_alerts,
        confidence=confidence,
        fishing_context=fishing_context,
        context_factors={
            "method": method_factor,
            "distance": distance_factor,
            "target_zone": target_zone_factor,
            "spot": spot_factor,
        },
    )

    return FishingScoreResult(
        species_id=profile.id,
        species_name=profile.name,
        score=final_score,
        base_score=weather_score,
        category=category,
        explanation=explanation,
        safety_alerts=safety_alerts,
        confidence=confidence,
        missing_fields=sorted(set(missing_fields)),
        factor_scores={key: round(value, 3) for key, value in factor_scores.items()},
        seasonality_factor=round(seasonality_factor, 2),
        method_factor=round(method_factor, 3),
        distance_factor=round(distance_factor, 3),
        target_zone_factor=round(target_zone_factor, 3),
        spot_factor=round(spot_factor, 3),
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


def calculate_target_zone(casting_distance_m: float) -> str:
    distance = max(0.0, float(casting_distance_m))
    if distance <= 5:
        return "shoreline"
    if distance <= 20:
        return "shore_break"
    if distance <= 50:
        return "inner_reef"
    if distance <= 100:
        return "outer_reef"
    return "deep_cast"


def build_fishing_context(
    fishing_method: str,
    casting_distance_m: float,
    target_zone: str | None = None,
    water_column: str | None = None,
    spot_type: str | None = None,
    shore_type: str | None = None,
    spot_exposure: str | None = None,
    water_depth_estimate_m: float | None = None,
) -> FishingContext:
    method = fishing_method if fishing_method in ALLOWED_FISHING_METHODS else "float"
    distance = max(0.0, float(casting_distance_m))
    zone = target_zone if target_zone in ALLOWED_TARGET_ZONES else calculate_target_zone(distance)
    column = water_column if water_column in ALLOWED_WATER_COLUMNS else _default_water_column(method)
    return FishingContext(
        fishing_method=method,
        casting_distance_m=distance,
        target_zone=zone,
        water_column=column,
        spot_type=spot_type or None,
        shore_type=shore_type or None,
        spot_exposure=spot_exposure or None,
        water_depth_estimate_m=water_depth_estimate_m,
    )


def get_species_distance_factor(species_id: str, casting_distance_m: float) -> float:
    distance = max(0.0, float(casting_distance_m))
    profile = SPECIES_DISTANCE_PROFILES.get(species_id)
    if not profile:
        return 1.0
    for distance_range in profile:
        if distance_range["min"] <= distance < distance_range["max"]:
            return distance_range["factor"]
    return 0.5


def serialize_fishing_context(fishing_context: FishingContext) -> dict:
    return {
        "fishing_method": fishing_context.fishing_method,
        "fishing_method_label": FISHING_METHOD_LABELS.get(fishing_context.fishing_method, fishing_context.fishing_method),
        "casting_distance_m": round(fishing_context.casting_distance_m, 1),
        "target_zone": fishing_context.target_zone,
        "target_zone_label": TARGET_ZONE_LABELS.get(fishing_context.target_zone, fishing_context.target_zone),
        "water_column": fishing_context.water_column,
        "spot_type": fishing_context.spot_type,
        "shore_type": fishing_context.shore_type,
        "spot_exposure": fishing_context.spot_exposure,
        "water_depth_estimate_m": fishing_context.water_depth_estimate_m,
        "interpretation": fishing_context_interpretation(fishing_context),
    }


def fishing_context_interpretation(fishing_context: FishingContext) -> str:
    method = fishing_context.fishing_method
    distance = fishing_context.casting_distance_m
    if method == "float" and distance <= 30:
        return (
            "Estas pescando cerca de costa, entre 0 y 30 m. "
            "Esta zona favorece especies de rompiente como sargo, chopa, vieja, boga y roncador. "
            "La espuma moderada y el agua algo movida pueden mejorar la actividad."
        )
    if method == "spinning" and distance <= 30:
        return (
            "Estas haciendo spinning corto en proximidad costera. "
            "La primera rompiente favorece depredadores pequenos y especies de espuma, "
            "pero limita especies de lance largo."
        )
    if method == "bottom" and 50 <= distance <= 100:
        return (
            f"Estas pescando a fondo con lance largo, aproximadamente a {distance:.0f} m desde costa. "
            "Esta distancia favorece especies de zonas exteriores como sama, bocinegro, medregal o dorado."
        )
    if method == "lure_trolling_like":
        return (
            f"Estas trabajando un senuelo en avance a unos {distance:.0f} m desde costa, "
            "compatible con capas de agua de superficie o media agua."
        )
    zone_label = TARGET_ZONE_LABELS.get(fishing_context.target_zone, fishing_context.target_zone)
    method_label = FISHING_METHOD_LABELS.get(method, method)
    return f"{method_label} a {distance:.0f} m desde costa, en {zone_label}."


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


def _default_water_column(fishing_method: str) -> str:
    if fishing_method == "bottom":
        return "bottom"
    if fishing_method in {"spinning", "lure_trolling_like"}:
        return "mid_water"
    return "surface"


def _context_factors(
    conditions: FishingConditions,
    profile: SpeciesProfile,
    fishing_context: FishingContext | None,
) -> tuple[float, float, float, float]:
    if fishing_context is None or profile.id == "general":
        return 1.0, 1.0, 1.0, 1.0

    method_factor = FISHING_METHOD_FACTORS.get(fishing_context.fishing_method, 1.0)
    distance_factor = get_species_distance_factor(profile.id, fishing_context.casting_distance_m)
    target_zone_factor = _target_zone_factor(profile.id, fishing_context.target_zone)
    spot_factor = _spot_factor(conditions, profile, fishing_context)
    return method_factor, distance_factor, target_zone_factor, spot_factor


def _target_zone_factor(species_id: str, target_zone: str) -> float:
    return SPECIES_TARGET_ZONE_FACTORS.get(species_id, {}).get(target_zone, 1.0)


def _spot_factor(conditions: FishingConditions, profile: SpeciesProfile, fishing_context: FishingContext) -> float:
    factor = 1.0
    method = fishing_context.fishing_method
    distance = fishing_context.casting_distance_m
    target_zone = fishing_context.target_zone
    spot_type = (fishing_context.spot_type or "").lower()
    shore_type = (fishing_context.shore_type or "").lower()
    exposure = (fishing_context.spot_exposure or "").lower()

    if spot_type in {"rocky", "reef", "mixed"} and profile.id in ROCK_AND_REEF_SPECIES:
        factor *= 1.05
    elif spot_type == "sandy" and profile.id in ROCK_AND_REEF_SPECIES:
        factor *= 0.92

    if shore_type == "volcanic" and profile.id in ROCK_AND_REEF_SPECIES:
        factor *= 1.03
    elif shore_type == "beach" and profile.id in {"pulpo", "vieja_pejeverde", "catalufa"}:
        factor *= 0.94

    is_short_coast = method in {"float", "spinning"} and distance <= 30 and target_zone in {"shoreline", "shore_break"}
    if is_short_coast:
        if exposure == "semi_exposed":
            factor *= 1.04
        elif exposure == "exposed":
            factor *= 0.9
        elif exposure == "sheltered":
            factor *= 0.96

        if conditions.wave_height_m is not None:
            wave = conditions.wave_height_m
            if 0.4 <= wave <= 1.3:
                factor *= 1.08
            elif wave < 0.2:
                factor *= 0.9
            elif wave >= 1.8:
                factor *= 0.82

        if conditions.wind_speed_ms is not None and conditions.wind_speed_ms >= 9:
            factor *= 0.9

        if _time_phase(conditions, []) in {"dawn", "dusk"}:
            factor *= 1.05

    is_long_bottom = method == "bottom" and 50 <= distance <= 100
    if is_long_bottom:
        if profile.id in LONG_CAST_SPECIES:
            factor *= 1.04
        if spot_type in {"rocky", "reef", "mixed"}:
            factor *= 1.03
        if fishing_context.water_depth_estimate_m is not None and fishing_context.water_depth_estimate_m >= 8:
            factor *= 1.03

    return max(0.65, min(1.25, factor))


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
    fishing_context: FishingContext | None = None,
    context_factors: dict[str, float] | None = None,
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
    if positives and negatives:
        parts.append(
            f"Balance mixto: ayudan {FACTOR_LABELS[positives[0][0]]} y {FACTOR_LABELS[positives[1][0]] if len(positives) > 1 else FACTOR_LABELS[positives[0][0]]}, "
            f"pero penalizan {FACTOR_LABELS[negatives[0][0]]}."
        )
    elif positives:
        parts.append("Tramo favorable con mar y condiciones bastante ordenadas.")
    elif negatives:
        parts.append("Tramo flojo por condiciones poco comodas para pescar desde costa.")
    else:
        parts.append("Condiciones sin una ventaja clara.")

    if safety_alerts:
        parts.append("Alerta: " + safety_alerts[0])

    seasonality = _seasonality_factor(month, profile)
    if seasonality <= 0.35 and profile.id != "general":
        parts.append("Es mes flojo para esta especie.")
    elif seasonality >= 0.85 and profile.id != "general":
        parts.append("La estacionalidad acompana.")

    if confidence != "alta":
        parts.append(f"Confianza {confidence} por datos incompletos.")

    context_text = _context_explanation(profile, fishing_context, context_factors or {})
    if context_text:
        parts.append(context_text)

    return " ".join(parts)


def _context_explanation(
    profile: SpeciesProfile,
    fishing_context: FishingContext | None,
    context_factors: dict[str, float],
) -> str:
    if fishing_context is None or profile.id == "general":
        return ""

    method = fishing_context.fishing_method
    distance = fishing_context.casting_distance_m
    zone_label = TARGET_ZONE_LABELS.get(fishing_context.target_zone, fishing_context.target_zone)
    distance_factor = context_factors.get("distance", 1.0)
    spot_factor = context_factors.get("spot", 1.0)

    if method == "float" and distance <= 30 and distance_factor >= 0.85:
        return f"Muy compatible con boya/spinning corto en {zone_label}."

    if method in {"float", "spinning"} and distance <= 30 and distance_factor <= 0.25:
        return (
            f"Poco compatible con pesca a {distance:.0f} m desde costa; "
            "suele ser mas favorable con lances largos o zonas exteriores."
        )

    if method == "bottom" and 50 <= distance <= 100 and distance_factor >= 0.85:
        return f"La distancia de lance largo encaja bien con {profile.name.lower()}."

    if distance_factor <= 0.35:
        return f"La distancia de {distance:.0f} m penaliza a esta especie frente a su zona ideal."

    if spot_factor >= 1.08:
        return "El tipo de spot y las condiciones de rompiente suman compatibilidad."

    if distance_factor >= 0.85:
        return f"La distancia de lance encaja bien con su zona habitual en {zone_label}."

    if distance_factor < 0.65:
        return f"Compatibilidad media-baja por distancia de lance en {zone_label}."

    return ""


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
