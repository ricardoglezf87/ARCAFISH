import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, utcnow
from app.models import FishingSpot, ForecastCache
from app.services.forecast_service import (
    ForecastService,
    STALE_PROVIDER_WARNING,
    _current_or_first_row,
    _merge_weather_payloads,
    _rows_for_next_24h,
    _summary_weights,
)


def _row(dt_text: str, score: int = 50) -> dict:
    return {
        "datetime": dt_text,
        "wind_speed_ms": None,
        "wave_height_m": None,
        "fishing_score": score,
        "fishing_category": "Regular",
        "safety_alerts": [],
        "species_scores": {"general": {"score": score}},
    }


class _DelayedProvider:
    def __init__(self, name: str, probe: dict) -> None:
        self.name = name
        self.probe = probe

    async def fetch(self, latitude: float, longitude: float, days: int) -> dict:
        self.probe["active"] += 1
        self.probe["max_active"] = max(self.probe["max_active"], self.probe["active"])
        await asyncio.sleep(0.01)
        self.probe["active"] -= 1
        return {"provider": self.name, "latitude": latitude, "longitude": longitude, "days": days}


class _FailingProvider:
    async def fetch(self, latitude: float, longitude: float, days: int) -> dict:
        raise RuntimeError("provider down")


def test_external_forecast_requests_run_concurrently():
    probe = {"active": 0, "max_active": 0}
    service = ForecastService(db=None)
    service.weather_provider = _DelayedProvider("weather", probe)
    service.weather_ensemble_providers = []
    service.marine_provider = _DelayedProvider("marine", probe)
    spot = SimpleNamespace(latitude=28.1, longitude=-16.5)

    weather, marine = asyncio.run(service._fetch_external_data(spot))

    assert weather["provider"] == "weather"
    assert marine["provider"] == "marine"
    assert probe["max_active"] == 2


def test_rows_for_next_24h_uses_real_24_hour_window():
    tz = ZoneInfo("Atlantic/Canary")
    now_local = datetime(2026, 5, 20, 10, 30, tzinfo=tz)
    rows = [
        _row("2026-05-20T00:00:00+01:00"),
        _row("2026-05-20T10:00:00+01:00"),
        _row("2026-05-20T11:00:00+01:00"),
        _row("2026-05-21T10:00:00+01:00"),
        _row("2026-05-21T11:00:00+01:00"),
    ]

    window = _rows_for_next_24h(rows, now_local)

    assert [row["datetime"] for row in window] == [
        "2026-05-20T11:00:00+01:00",
        "2026-05-21T10:00:00+01:00",
    ]


def test_current_or_first_row_picks_first_future_row():
    tz = ZoneInfo("Atlantic/Canary")
    now_local = datetime(2026, 5, 20, 10, 30, tzinfo=tz)
    rows = [
        _row("2026-05-20T00:00:00+01:00"),
        _row("2026-05-20T10:00:00+01:00"),
        _row("2026-05-20T11:00:00+01:00"),
    ]

    current = _current_or_first_row(rows, now_local)

    assert current["datetime"] == "2026-05-20T11:00:00+01:00"


def test_summary_weights_support_full_hourly_day():
    weights = _summary_weights(24)

    assert len(weights) == 24
    assert weights[0] == 1.0
    assert weights[-1] >= 0.25


def test_expired_cache_can_be_returned_as_stale_forecast():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        spot = FishingSpot(name="Punta test", latitude=28.1, longitude=-16.5)
        db.add(spot)
        db.commit()
        db.refresh(spot)

        service = ForecastService(db)
        now = utcnow()
        forecast_time = datetime.now(ZoneInfo(service.settings.canary_timezone)).replace(
            minute=0,
            second=0,
            microsecond=0,
        ) + timedelta(hours=1)
        raw_forecast = {
            "spot": {
                "id": spot.id,
                "name": spot.name,
                "latitude": spot.latitude,
                "longitude": spot.longitude,
            },
            "summary": {},
            "hourly": [_row(forecast_time.isoformat(), score=55)],
            "meta": {
                "cached": False,
                "forecast_days": service.settings.forecast_days,
            },
        }
        db.add(
            ForecastCache(
                spot_id=spot.id,
                provider=service.provider_name,
                forecast_datetime=now - timedelta(hours=2),
                raw_data=raw_forecast,
                created_at=now - timedelta(hours=2),
                expires_at=now - timedelta(minutes=1),
            )
        )
        db.commit()

        forecast = service.get_cached_forecast(spot, allow_expired=True)

        assert forecast is not None
        assert forecast["meta"]["cached"] is True
        assert forecast["meta"]["stale"] is True
        assert "actualizando pronostico" in forecast["meta"]["warning"]
        assert forecast["summary"]["species"]
    finally:
        db.close()


def test_failed_refresh_uses_last_cache_with_clear_warning():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        spot = FishingSpot(name="Punta test", latitude=28.1, longitude=-16.5)
        db.add(spot)
        db.commit()
        db.refresh(spot)

        service = ForecastService(db)
        service.weather_provider = _FailingProvider()
        service.weather_ensemble_providers = []
        service.marine_provider = _FailingProvider()
        now = utcnow()
        forecast_time = datetime.now(ZoneInfo(service.settings.canary_timezone)).replace(
            minute=0,
            second=0,
            microsecond=0,
        ) + timedelta(hours=1)
        raw_forecast = {
            "spot": {
                "id": spot.id,
                "name": spot.name,
                "latitude": spot.latitude,
                "longitude": spot.longitude,
            },
            "summary": {},
            "hourly": [_row(forecast_time.isoformat(), score=55)],
            "meta": {
                "cached": False,
                "forecast_days": service.settings.forecast_days,
            },
        }
        db.add(
            ForecastCache(
                spot_id=spot.id,
                provider=service.provider_name,
                forecast_datetime=now - timedelta(hours=2),
                raw_data=raw_forecast,
                created_at=now - timedelta(hours=2),
                expires_at=now - timedelta(minutes=1),
            )
        )
        db.commit()

        forecast = asyncio.run(service.get_forecast(spot, force_refresh=True))

        assert forecast["meta"]["cached"] is True
        assert forecast["meta"]["stale"] is True
        assert forecast["meta"]["warning"] == STALE_PROVIDER_WARNING
    finally:
        db.close()


def test_weather_ensemble_averages_comparable_fields():
    open_meteo = {
        "hourly": {
            "time": ["2026-05-28T10:00", "2026-05-28T11:00"],
            "temperature_2m": [20.0, 22.0],
            "precipitation": [0.0, 1.0],
            "pressure_msl": [1012.0, 1014.0],
            "cloud_cover": [20.0, 60.0],
            "wind_speed_10m": [4.0, 6.0],
            "wind_gusts_10m": [7.0, 9.0],
            "wind_direction_10m": [350.0, 90.0],
            "weather_code": [0, 3],
            "is_day": [1, 1],
        }
    }
    metno = {
        "hourly": {
            "time": ["2026-05-28T10:00", "2026-05-28T11:00"],
            "temperature_2m": [24.0, 26.0],
            "precipitation": [0.2, 3.0],
            "pressure_msl": [1010.0, 1012.0],
            "cloud_cover": [40.0, 80.0],
            "wind_speed_10m": [6.0, 8.0],
            "wind_gusts_10m": [9.0, 11.0],
            "wind_direction_10m": [10.0, 180.0],
            "weather_code": [1, 61],
            "is_day": [1, 1],
        }
    }

    merged = _merge_weather_payloads([("open-meteo-weather", open_meteo), ("met-no-locationforecast", metno)])

    assert merged["_arcafish_weather_meta"]["ensemble"] is True
    assert merged["_arcafish_weather_meta"]["providers"] == ["open-meteo-weather", "met-no-locationforecast"]
    assert merged["hourly"]["temperature_2m"] == [22.0, 24.0]
    assert merged["hourly"]["precipitation"] == [0.1, 2.0]
    assert merged["hourly"]["pressure_msl"] == [1011.0, 1013.0]
    assert merged["hourly"]["cloud_cover"] == [30.0, 70.0]
    assert merged["hourly"]["wind_speed_10m"] == [5.0, 7.0]
    assert merged["hourly"]["wind_direction_10m"] == [0, 135]


def test_store_cache_replaces_previous_cache_rows_for_spot():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        spot = FishingSpot(name="Punta test", latitude=28.1, longitude=-16.5)
        db.add(spot)
        db.commit()
        db.refresh(spot)

        service = ForecastService(db)
        first_forecast = {
            "spot": {"id": spot.id, "name": "Antigua", "latitude": spot.latitude, "longitude": spot.longitude},
            "summary": {},
            "hourly": [],
            "meta": {"forecast_days": service.settings.forecast_days},
        }
        second_forecast = {
            "spot": {"id": spot.id, "name": "Nueva", "latitude": spot.latitude, "longitude": spot.longitude},
            "summary": {},
            "hourly": [],
            "meta": {"forecast_days": service.settings.forecast_days},
        }

        service._store_cache(spot.id, first_forecast)
        service._store_cache(spot.id, second_forecast)

        rows = db.query(ForecastCache).filter(ForecastCache.spot_id == spot.id).all()
        assert len(rows) == 1
        assert rows[0].raw_data["spot"]["name"] == "Nueva"
    finally:
        db.close()
