from datetime import datetime, timedelta, timezone

from app.services.fishing_score import (
    FISHING_METHOD_LABELS,
    FishingConditions,
    build_fishing_context,
    calculate_fishing_score,
    calculate_target_zone,
)


def base_conditions(**overrides):
    sunrise = datetime(2026, 5, 19, 7, 12, tzinfo=timezone.utc)
    sunset = datetime(2026, 5, 19, 20, 48, tzinfo=timezone.utc)
    values = {
        "datetime": sunset - timedelta(minutes=30),
        "wind_speed_ms": 5.0,
        "wind_gust_ms": 7.0,
        "temperature_c": 21.0,
        "sea_surface_temperature_c": 22.0,
        "precipitation_mm": 0.0,
        "cloud_cover_percent": 45.0,
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


def test_general_score_is_good_but_not_perfect_in_a_typical_good_window():
    result = calculate_fishing_score(base_conditions())

    assert 60 <= result.score <= 90
    assert result.category in {"Buena", "Muy buena"}
    assert result.safety_alerts == []
    assert result.confidence == "alta"


def test_dangerous_wave_caps_score_and_adds_alert():
    result = calculate_fishing_score(base_conditions(wave_height_m=3.0, wave_period_s=13.0))

    assert result.score <= 39
    assert result.category == "Mala"
    assert any("Oleaje" in alert for alert in result.safety_alerts)


def test_missing_marine_data_lowers_confidence():
    result = calculate_fishing_score(
        base_conditions(wave_height_m=None, wave_period_s=None, tide_state=None, sea_surface_temperature_c=None)
    )

    assert result.confidence == "media"
    assert "wave_height_m" in result.missing_fields
    assert "tide_state" in result.missing_fields


def test_pulpo_scores_better_at_night_than_midday():
    night_result = calculate_fishing_score(
        base_conditions(
            datetime=datetime(2026, 5, 19, 22, 30, tzinfo=timezone.utc),
            is_day=False,
            wave_height_m=0.4,
            tide_state="bajando",
        ),
        "pulpo",
    )
    midday_result = calculate_fishing_score(
        base_conditions(
            datetime=datetime(2026, 5, 19, 14, 0, tzinfo=timezone.utc),
            is_day=True,
            wave_height_m=0.4,
            tide_state="bajando",
        ),
        "pulpo",
    )

    assert night_result.score > midday_result.score


def test_dorado_prefers_warmer_daylight_conditions():
    warm_day = calculate_fishing_score(
        base_conditions(
            datetime=datetime(2026, 5, 19, 11, 0, tzinfo=timezone.utc),
            is_day=True,
            sea_surface_temperature_c=26.0,
            cloud_cover_percent=10.0,
        ),
        "dorado",
    )
    cool_night = calculate_fishing_score(
        base_conditions(
            datetime=datetime(2026, 5, 19, 22, 0, tzinfo=timezone.utc),
            is_day=False,
            sea_surface_temperature_c=20.0,
            cloud_cover_percent=80.0,
        ),
        "dorado",
    )

    assert warm_day.score > cool_night.score


def test_seasonality_penalizes_dorado_in_winter_against_summer():
    january = calculate_fishing_score(
        base_conditions(datetime=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc), sea_surface_temperature_c=25.5),
        "dorado",
    )
    august = calculate_fishing_score(
        base_conditions(datetime=datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc), sea_surface_temperature_c=25.5),
        "dorado",
    )

    assert january.seasonality_factor < august.seasonality_factor
    assert january.score < august.score


def test_target_zone_is_calculated_from_horizontal_casting_distance():
    context = build_fishing_context(
        fishing_method="float",
        casting_distance_m=18,
        water_depth_estimate_m=80,
    )

    assert calculate_target_zone(4) == "shoreline"
    assert calculate_target_zone(18) == "shore_break"
    assert calculate_target_zone(80) == "outer_reef"
    assert context.target_zone == "shore_break"
    assert context.water_depth_estimate_m == 80


def test_float_short_cast_favors_breakwater_species_and_penalizes_sama():
    context = build_fishing_context(
        fishing_method="float",
        casting_distance_m=18,
        spot_type="rocky",
        shore_type="volcanic",
        spot_exposure="semi_exposed",
    )

    sargo = calculate_fishing_score(base_conditions(), "sargo_chopa_roncador", context)
    sama = calculate_fishing_score(base_conditions(), "bocinegro_sama", context)

    assert sargo.distance_factor == 1.0
    assert sama.distance_factor == 0.1
    assert sargo.score > sama.score
    assert "Muy compatible" in sargo.explanation
    assert "Poco compatible" in sama.explanation


def test_bottom_long_cast_favors_outer_zone_species():
    short_context = build_fishing_context(fishing_method="float", casting_distance_m=18)
    long_context = build_fishing_context(
        fishing_method="bottom",
        casting_distance_m=80,
        spot_type="rocky",
        shore_type="volcanic",
        spot_exposure="semi_exposed",
        water_depth_estimate_m=12,
    )

    short_sama = calculate_fishing_score(base_conditions(), "bocinegro_sama", short_context)
    long_sama = calculate_fishing_score(base_conditions(), "bocinegro_sama", long_context)

    assert long_context.target_zone == "outer_reef"
    assert long_sama.distance_factor == 1.0
    assert long_sama.score > short_sama.score


def test_fishing_methods_are_float_bottom_and_spinning():
    assert set(FISHING_METHOD_LABELS) == {"float", "bottom", "spinning"}
    assert FISHING_METHOD_LABELS["spinning"] == "Spinning / rockfishing"
