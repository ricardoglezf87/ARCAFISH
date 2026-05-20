from typing import Protocol

import httpx

from app.config import Settings, get_settings


class MarineProvider(Protocol):
    provider_name: str

    async def fetch(self, latitude: float, longitude: float, days: int) -> dict:
        ...


class OpenMeteoMarineProvider:
    provider_name = "open-meteo-marine"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def fetch(self, latitude: float, longitude: float, days: int) -> dict:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": self.settings.canary_timezone,
            "forecast_days": min(days, 8),
            "timeformat": "iso8601",
            "length_unit": "metric",
            "cell_selection": "sea",
            "hourly": ",".join(
                [
                    "wave_height",
                    "wave_direction",
                    "wave_period",
                    "sea_level_height_msl",
                    "sea_surface_temperature",
                ]
            ),
        }
        async with httpx.AsyncClient(
            timeout=self.settings.http_timeout_seconds,
            verify=self.settings.http_verify_ssl,
        ) as client:
            response = await client.get(self.settings.open_meteo_marine_url, params=params)
            response.raise_for_status()
            payload = response.json()
        if payload.get("error"):
            raise RuntimeError(payload.get("reason", "Open-Meteo Marine devolvió un error."))
        return payload
