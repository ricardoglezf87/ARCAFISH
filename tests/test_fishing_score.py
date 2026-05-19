from datetime import datetime, timedelta, timezone

from app.services.fishing_score import FishingConditions, calculate_fishing_score


def base_conditions(**overrides):
    sunrise = datetime(2026, 5, 19, 7, 12, tzinfo=timezone.utc)
    sunset = datetime(2026, 5, 19, 20, 48, tzinfo=timezone.utc)
    values = {
        "datetime": sunset - timedelta(minutes=30),
        "wind_speed_ms": 5.0,
        "wind_gust_ms": 7.0,
        "temperature_c": 21.0,
        "precipitation_mm": 0.0,
        "pressure_hpa": 1017.0,
        "pressure_trend_hpa": 0.3,
        "wave_height_m": 1.0,
        "wave_period_s": 8.0,
        "tide_state": "subiendo",
        "moon_phase": "llena",
        "sunrise": sunrise,
        "sunset": sunset,
        "is_day": True,
    }
    values.update(overrides)
    return FishingConditions(**values)


def test_good_evening_incoming_tide_scores_high():
    result = calculate_fishing_score(base_conditions())

    assert result.score >= 80
    assert result.category == "Muy buena"
    assert result.safety_alerts == []
    assert result.confidence == "alta"


def test_dangerous_wave_caps_score_and_adds_alert():
    result = calculate_fishing_score(base_conditions(wave_height_m=3.0, wave_period_s=13.0))

    assert result.score <= 39
    assert result.category == "Mala"
    assert any("Oleaje peligroso" in alert for alert in result.safety_alerts)


def test_missing_marine_data_lowers_confidence():
    result = calculate_fishing_score(base_conditions(wave_height_m=None, wave_period_s=None, tide_state=None))

    assert result.confidence == "media"
    assert "wave_height_m" in result.missing_fields
    assert "tide_state" in result.missing_fields

