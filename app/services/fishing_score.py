from dataclasses import dataclass, field
from datetime import datetime, timedelta


WIND_IDEAL_MIN_MS = 2.0
WIND_IDEAL_MAX_MS = 7.0
WIND_STRONG_MS = 10.0
WIND_DANGEROUS_MS = 14.0

GUST_STRONG_MS = 13.0
GUST_DANGEROUS_MS = 18.0

WAVE_IDEAL_MIN_M = 0.4
WAVE_IDEAL_MAX_M = 1.5
WAVE_STRONG_M = 2.0
WAVE_DANGEROUS_M = 2.5

RAIN_MODERATE_MM = 1.5
RAIN_HEAVY_MM = 4.0

PRESSURE_LOW_HPA = 1008.0
PRESSURE_STABLE_MAX_CHANGE_HPA = 1.0
PRESSURE_FAST_DROP_HPA = -2.0


@dataclass(frozen=True)
class FishingConditions:
    datetime: datetime
    wind_speed_ms: float | None = None
    wind_gust_ms: float | None = None
    wind_direction_deg: float | None = None
    temperature_c: float | None = None
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
class FishingScoreResult:
    score: int
    category: str
    explanation: str
    safety_alerts: list[str]
    confidence: str
    missing_fields: list[str]


def calculate_fishing_score(conditions: FishingConditions) -> FishingScoreResult:
    score = 55.0
    positives: list[str] = []
    cautions: list[str] = []
    safety_alerts: list[str] = []
    missing_fields = list(conditions.missing_fields)

    score += _score_wind(conditions, positives, cautions, safety_alerts, missing_fields)
    score += _score_waves(conditions, positives, cautions, safety_alerts, missing_fields)
    score += _score_rain(conditions, positives, cautions, missing_fields)
    score += _score_temperature(conditions, positives, cautions, missing_fields)
    score += _score_pressure(conditions, positives, cautions, missing_fields)
    score += _score_tide(conditions, positives, cautions, missing_fields)
    score += _score_time_window(conditions, positives)
    score += _score_moon(conditions, positives)

    if missing_fields:
        score -= min(10, len(set(missing_fields)) * 2)

    cap = _safety_cap(conditions, safety_alerts)
    if cap is not None:
        score = min(score, cap)

    final_score = int(round(max(0, min(100, score))))
    category = score_category(final_score)
    confidence = _confidence(missing_fields)
    explanation = _build_explanation(positives, cautions, safety_alerts, confidence)

    return FishingScoreResult(
        score=final_score,
        category=category,
        explanation=explanation,
        safety_alerts=list(dict.fromkeys(safety_alerts)),
        confidence=confidence,
        missing_fields=sorted(set(missing_fields)),
    )


def score_category(score: int) -> str:
    if score <= 39:
        return "Mala"
    if score <= 59:
        return "Regular"
    if score <= 79:
        return "Buena"
    return "Muy buena"


def _score_wind(
    conditions: FishingConditions,
    positives: list[str],
    cautions: list[str],
    safety_alerts: list[str],
    missing_fields: list[str],
) -> float:
    score = 0.0
    wind = conditions.wind_speed_ms
    gust = conditions.wind_gust_ms

    if wind is None:
        missing_fields.append("wind_speed_ms")
    elif wind < WIND_IDEAL_MIN_MS:
        score -= 4
        cautions.append("viento muy flojo")
    elif wind <= WIND_IDEAL_MAX_MS:
        score += 12
        positives.append("viento moderado")
    elif wind <= WIND_STRONG_MS:
        score += 4
        positives.append("viento manejable")
    elif wind <= WIND_DANGEROUS_MS:
        score -= 12
        cautions.append("viento fuerte")
    else:
        score -= 30
        safety_alerts.append("Viento fuerte para pesca desde costa.")

    if gust is None:
        missing_fields.append("wind_gust_ms")
    elif gust <= WIND_IDEAL_MAX_MS + 2:
        score += 4
    elif gust <= GUST_STRONG_MS:
        score -= 4
        cautions.append("rachas algo intensas")
    elif gust <= GUST_DANGEROUS_MS:
        score -= 12
        safety_alerts.append("Rachas intensas; extrema la precaucion.")
    else:
        score -= 25
        safety_alerts.append("Rachas peligrosas para pescar en roca o espigon.")
    return score


def _score_waves(
    conditions: FishingConditions,
    positives: list[str],
    cautions: list[str],
    safety_alerts: list[str],
    missing_fields: list[str],
) -> float:
    score = 0.0
    wave = conditions.wave_height_m
    period = conditions.wave_period_s

    if wave is None:
        missing_fields.append("wave_height_m")
    elif wave < 0.3:
        score -= 4
        cautions.append("mar demasiado plano")
    elif WAVE_IDEAL_MIN_M <= wave <= WAVE_IDEAL_MAX_M:
        score += 14
        positives.append("oleaje manejable")
    elif wave <= WAVE_STRONG_M:
        score += 2
        cautions.append("oleaje que exige atencion")
    elif wave <= WAVE_DANGEROUS_M:
        score -= 18
        safety_alerts.append("Oleaje alto; evita zonas expuestas.")
    else:
        score -= 35
        safety_alerts.append("Oleaje peligroso para pesca desde costa.")

    if period is None:
        missing_fields.append("wave_period_s")
    elif 6 <= period <= 11:
        score += 5
        positives.append("periodo de ola favorable")
    elif period >= 12 and wave is not None and wave >= WAVE_IDEAL_MAX_M:
        score -= 8
        cautions.append("mar de fondo con energia")
    elif period < 5:
        score -= 3
        cautions.append("mar corta")
    return score


def _score_rain(
    conditions: FishingConditions,
    positives: list[str],
    cautions: list[str],
    missing_fields: list[str],
) -> float:
    rain = conditions.precipitation_mm
    if rain is None:
        missing_fields.append("precipitation_mm")
        return 0
    if rain == 0:
        positives.append("sin lluvia prevista")
        return 3
    if rain >= RAIN_HEAVY_MM:
        cautions.append("lluvia intensa")
        return -12
    if rain >= RAIN_MODERATE_MM:
        cautions.append("lluvia moderada")
        return -6
    return -1


def _score_temperature(
    conditions: FishingConditions,
    positives: list[str],
    cautions: list[str],
    missing_fields: list[str],
) -> float:
    temp = conditions.temperature_c
    if temp is None:
        missing_fields.append("temperature_c")
        return 0
    if 17 <= temp <= 24:
        positives.append("temperatura comoda")
        return 4
    if 14 <= temp <= 28:
        return 1
    cautions.append("temperatura poco comoda")
    return -3


def _score_pressure(
    conditions: FishingConditions,
    positives: list[str],
    cautions: list[str],
    missing_fields: list[str],
) -> float:
    pressure = conditions.pressure_hpa
    trend = conditions.pressure_trend_hpa
    score = 0.0

    if pressure is None:
        missing_fields.append("pressure_hpa")
    elif pressure < PRESSURE_LOW_HPA:
        score -= 6
        cautions.append("presion baja")
    elif 1012 <= pressure <= 1022:
        score += 5
        positives.append("presion razonable")
    elif pressure > 1028:
        score -= 2

    if trend is None:
        missing_fields.append("pressure_trend_hpa")
    elif trend <= PRESSURE_FAST_DROP_HPA:
        score -= 8
        cautions.append("presion bajando rapido")
    elif abs(trend) <= PRESSURE_STABLE_MAX_CHANGE_HPA:
        score += 4
        positives.append("presion estable")
    return score


def _score_tide(
    conditions: FishingConditions,
    positives: list[str],
    cautions: list[str],
    missing_fields: list[str],
) -> float:
    state = (conditions.tide_state or "").lower()
    if not state or state == "sin datos":
        missing_fields.append("tide_state")
        return 0
    if state == "subiendo":
        positives.append("marea subiendo")
        return 10
    if state == "bajando":
        positives.append("marea en movimiento")
        return 5
    if state in {"pleamar", "bajamar"}:
        cautions.append(f"cerca de {state}")
        return -3
    return 0


def _score_time_window(conditions: FishingConditions, positives: list[str]) -> float:
    if not conditions.sunrise or not conditions.sunset:
        return 0
    moment = conditions.datetime
    if _within(moment, conditions.sunrise, 90) or _within(moment, conditions.sunset, 90):
        positives.append("franja de amanecer o atardecer")
        return 10
    if conditions.is_day is False:
        positives.append("horario nocturno")
        return 4
    return 0


def _score_moon(conditions: FishingConditions, positives: list[str]) -> float:
    phase = (conditions.moon_phase or "").lower()
    if phase in {"nueva", "llena"}:
        positives.append(f"luna {phase}")
        return 5
    if "cuarto" in phase or "creciente" in phase or "menguante" in phase:
        return 2
    return 0


def _safety_cap(conditions: FishingConditions, safety_alerts: list[str]) -> int | None:
    hard_alert = False
    caution_alert = False

    if conditions.wind_speed_ms is not None and conditions.wind_speed_ms > WIND_DANGEROUS_MS:
        hard_alert = True
    if conditions.wind_gust_ms is not None and conditions.wind_gust_ms > GUST_DANGEROUS_MS:
        hard_alert = True
    if conditions.wave_height_m is not None and conditions.wave_height_m > WAVE_DANGEROUS_M:
        hard_alert = True

    if conditions.wave_height_m is not None and conditions.wave_height_m >= WAVE_STRONG_M:
        caution_alert = True
    if conditions.wind_speed_ms is not None and conditions.wind_speed_ms >= WIND_STRONG_MS:
        caution_alert = True
    if conditions.wind_gust_ms is not None and conditions.wind_gust_ms >= GUST_STRONG_MS:
        caution_alert = True

    if hard_alert:
        return 39
    if caution_alert or safety_alerts:
        return 59
    return None


def _confidence(missing_fields: list[str]) -> str:
    missing_count = len(set(missing_fields))
    if missing_count <= 2:
        return "alta"
    if missing_count <= 5:
        return "media"
    return "baja"


def _build_explanation(
    positives: list[str],
    cautions: list[str],
    safety_alerts: list[str],
    confidence: str,
) -> str:
    unique_positives = list(dict.fromkeys(positives))
    unique_cautions = list(dict.fromkeys(cautions))
    parts: list[str] = []

    if unique_positives:
        parts.append("Buenas senales por " + ", ".join(unique_positives[:3]) + ".")
    else:
        parts.append("Condiciones sin ventajas claras para pesca desde costa.")

    if unique_cautions:
        parts.append("Precaucion por " + ", ".join(unique_cautions[:3]) + ".")
    if safety_alerts:
        parts.append("Alerta: " + safety_alerts[0])
    if confidence != "alta":
        parts.append(f"Confianza {confidence} por datos incompletos.")
    return " ".join(parts)


def _within(moment: datetime, target: datetime, minutes: int) -> bool:
    return abs(moment - target) <= timedelta(minutes=minutes)

