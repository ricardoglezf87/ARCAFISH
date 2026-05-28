from app.services.metno_weather_provider import MetNoWeatherProvider


def test_metno_payload_is_converted_to_internal_hourly_shape():
    provider = MetNoWeatherProvider()
    payload = {
        "geometry": {"coordinates": [-16.3, 28.4, 20]},
        "properties": {
            "meta": {"updated_at": "2026-05-28T09:00:00Z"},
            "timeseries": [
                {
                    "time": "2026-05-28T10:00:00Z",
                    "data": {
                        "instant": {
                            "details": {
                                "air_temperature": 22.4,
                                "air_pressure_at_sea_level": 1015.2,
                                "cloud_area_fraction": 35.0,
                                "wind_from_direction": 42.0,
                                "wind_speed": 4.3,
                                "wind_speed_of_gust": 7.8,
                            }
                        },
                        "next_1_hours": {
                            "summary": {"symbol_code": "partlycloudy_day"},
                            "details": {
                                "precipitation_amount": 0.1,
                                "probability_of_precipitation": 12.0,
                            },
                        },
                    },
                }
            ],
        },
    }

    converted = provider._to_open_meteo_shape(payload, days=1)

    assert converted["meta"]["provider"] == "met-no-locationforecast"
    assert converted["hourly"]["time"][0].startswith("2026-05-28T")
    assert converted["hourly"]["temperature_2m"] == [22.4]
    assert converted["hourly"]["pressure_msl"] == [1015.2]
    assert converted["hourly"]["cloud_cover"] == [35.0]
    assert converted["hourly"]["wind_direction_10m"] == [42.0]
    assert converted["hourly"]["weather_code"] == [2]
    assert converted["hourly"]["is_day"] == [1]
