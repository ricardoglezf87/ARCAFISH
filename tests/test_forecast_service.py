from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.forecast_service import (
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
