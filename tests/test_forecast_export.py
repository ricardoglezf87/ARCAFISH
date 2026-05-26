from app.services.forecast_export import build_forecast_pdf, filter_rows, resolve_species_exports


def sample_forecast() -> dict:
    return {
        "spot": {"id": 1, "name": "Punta test", "latitude": 28.1, "longitude": -16.5},
        "summary": {
            "score": 72,
            "category": "Buena",
            "recommendation": "Buen tramo en las proximas 24 horas.",
            "current_score": 68,
            "best_score": 79,
            "best_datetime": "2026-05-20T18:00:00+01:00",
            "safety_alerts": [],
            "species": {
                "dorado": {
                    "id": "dorado",
                    "name": "Dorado / Lampuga",
                    "score": 61,
                    "category": "Buena",
                    "recommendation": "Ventana favorable.",
                    "best_datetime": "2026-05-20T15:00:00+01:00",
                    "seasonality_factor": 0.6,
                }
            },
        },
        "hourly": [
            {
                "datetime": "2026-05-20T09:00:00+01:00",
                "weather_description": "Despejado",
                "wind_speed_ms": 4.2,
                "wind_gust_ms": 5.8,
                "precipitation_mm": 0.0,
                "precipitation_probability": 0,
                "wave_height_m": 0.9,
                "wave_period_s": 8,
                "tide_state": "subiendo",
                "tide_height_m": 1.3,
                "fishing_score": 70,
                "fishing_category": "Buena",
                "explanation": "Tramo favorable.",
                "species_scores": {
                    "dorado": {"score": 61, "category": "Buena", "explanation": "Algo activo."}
                },
            },
            {
                "datetime": "2026-05-20T12:00:00+01:00",
                "weather_description": "Parcialmente nuboso",
                "wind_speed_ms": 5.0,
                "wind_gust_ms": 7.0,
                "precipitation_mm": 0.0,
                "precipitation_probability": 5,
                "wave_height_m": 1.0,
                "wave_period_s": 8,
                "tide_state": "subiendo",
                "tide_height_m": 1.5,
                "fishing_score": 72,
                "fishing_category": "Buena",
                "explanation": "Buenas condiciones.",
                "species_scores": {
                    "dorado": {"score": 64, "category": "Buena", "explanation": "Mejora con el sol."}
                },
            },
            {
                "datetime": "2026-05-21T12:00:00+01:00",
                "weather_description": "Cubierto",
                "wind_speed_ms": 6.0,
                "wind_gust_ms": 8.2,
                "precipitation_mm": 0.4,
                "precipitation_probability": 25,
                "wave_height_m": 1.2,
                "wave_period_s": 9,
                "tide_state": "bajando",
                "tide_height_m": 0.9,
                "fishing_score": 60,
                "fishing_category": "Buena",
                "explanation": "Dia util.",
                "species_scores": {
                    "dorado": {"score": 54, "category": "Regular", "explanation": "Menos claro."}
                },
            },
        ],
        "meta": {
            "generated_at": "2026-05-20T08:15:00+00:00",
            "species_profiles": [{"id": "dorado", "name": "Dorado / Lampuga"}],
        },
    }


def test_filter_rows_respects_day_and_interval():
    rows = sample_forecast()["hourly"]

    filtered = filter_rows(rows, "2026-05-20", 3)

    assert len(filtered) == 2
    assert all(row["datetime"].startswith("2026-05-20") for row in filtered)


def test_filter_rows_aggregates_interval_averages():
    rows = [
        {
            "datetime": "2026-05-20T09:00:00+01:00",
            "weather_description": "Despejado",
            "wind_speed_ms": 4.0,
            "wind_direction_deg": 350,
            "fishing_score": 50,
            "fishing_category": "Regular",
            "species_scores": {"dorado": {"score": 40, "category": "Regular", "base_score": 42}},
        },
        {
            "datetime": "2026-05-20T10:00:00+01:00",
            "weather_description": "Despejado",
            "wind_speed_ms": 8.0,
            "wind_direction_deg": 10,
            "fishing_score": 70,
            "fishing_category": "Buena",
            "species_scores": {"dorado": {"score": 60, "category": "Buena", "base_score": 62}},
        },
    ]

    filtered = filter_rows(rows, "2026-05-20", 3)

    assert len(filtered) == 1
    assert filtered[0]["datetime"] == "2026-05-20T09:00:00+01:00"
    assert filtered[0]["period_end_datetime"] == "2026-05-20T12:00:00+01:00"
    assert filtered[0]["sample_count"] == 2
    assert filtered[0]["wind_speed_ms"] == 6.0
    assert filtered[0]["wind_direction_deg"] == 0
    assert filtered[0]["fishing_score"] == 60
    assert filtered[0]["fishing_category"] == "Buena"
    assert filtered[0]["species_scores"]["dorado"]["score"] == 50
    assert filtered[0]["species_scores"]["dorado"]["category"] == "Regular"


def test_resolve_species_exports_supports_selected_and_all():
    forecast = sample_forecast()

    selected = resolve_species_exports(forecast, "selected", "general")
    all_species = resolve_species_exports(forecast, "all", "dorado")

    assert selected[0].species_id == "general"
    assert [item.species_id for item in all_species] == ["general", "dorado"]


def test_build_forecast_pdf_returns_pdf_bytes():
    pdf = build_forecast_pdf(
        forecast=sample_forecast(),
        selected_day="2026-05-20",
        species_scope="selected",
        species_id="general",
        interval_hours=3,
    )

    assert pdf.startswith(b"%PDF")
