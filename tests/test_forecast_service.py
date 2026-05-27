import asyncio
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.services.forecast_service import (
    ForecastService,
    _current_or_first_row,
    _rows_for_next_24h,
    _summary_weights,
)


def _row(dt_text: str, score: int = 50) -> dict:
    return {
        "datetime": dt_text,
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


def test_external_forecast_requests_run_concurrently():
    probe = {"active": 0, "max_active": 0}
    service = ForecastService(db=None)
    service.weather_provider = _DelayedProvider("weather", probe)
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
