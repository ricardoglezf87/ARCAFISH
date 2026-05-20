from typing import Protocol

import httpx

from app.config import Settings, get_settings


class WeatherProvider(Protocol):
    provider_name: str

    async def fetch(self, latitude: float, longitude: float, days: int) -> dict:
        ...


class OpenMeteoWeatherProvider:
    provider_name = "open-meteo-weather"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def fetch(self, latitude: float, longitude: float, days: int) -> dict:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": self.settings.canary_timezone,
            "forecast_days": days,
            "wind_speed_unit": "ms",
            "timeformat": "iso8601",
            "hourly": ",".join(
                [
                    "temperature_2m",
                    "precipitation",
                    "precipitation_probability",
                    "pressure_msl",
                    "cloud_cover",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "wind_gusts_10m",
                    "is_day",
                ]
            ),
            "daily": "sunrise,sunset",
        }
        async with httpx.AsyncClient(
            timeout=self.settings.http_timeout_seconds,
            verify=self.settings.http_verify_ssl,
        ) as client:
            response = await client.get(self.settings.open_meteo_weather_url, params=params)
            response.raise_for_status()
            payload = response.json()
        if payload.get("error"):
            raise RuntimeError(payload.get("reason", "Open-Meteo Weather devolvió un error."))
        return payload
