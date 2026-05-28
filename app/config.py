import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    database_url: str
    canary_timezone: str
    forecast_days: int
    forecast_cache_ttl_minutes: int
    http_timeout_seconds: float
    http_verify_ssl: bool
    weather_ensemble_enabled: bool
    open_meteo_weather_url: str
    open_meteo_marine_url: str
    metno_weather_url: str
    metno_user_agent: str
    aemet_api_key: str | None
    stormglass_api_key: str | None
    worldtides_api_key: str | None
    canary_min_lat: float
    canary_max_lat: float
    canary_min_lon: float
    canary_max_lon: float

    def is_inside_canary_bounds(self, latitude: float, longitude: float) -> bool:
        return (
            self.canary_min_lat <= latitude <= self.canary_max_lat
            and self.canary_min_lon <= longitude <= self.canary_max_lon
        )


@lru_cache
def get_settings() -> Settings:
    _load_env_file()
    return Settings(
        app_name=_env("APP_NAME", "ARCAFISH"),
        environment=_env("ENVIRONMENT", "local"),
        database_url=_env("DATABASE_URL", "sqlite:///./arcafish.db"),
        canary_timezone=_env("CANARY_TIMEZONE", "Atlantic/Canary"),
        forecast_days=_env_int("FORECAST_DAYS", 7, minimum=1, maximum=8),
        forecast_cache_ttl_minutes=_env_int("FORECAST_CACHE_TTL_MINUTES", 60, minimum=5),
        http_timeout_seconds=_env_float("HTTP_TIMEOUT_SECONDS", 12.0, minimum=1.0),
        http_verify_ssl=_env_bool("HTTP_VERIFY_SSL", True),
        weather_ensemble_enabled=_env_bool("WEATHER_ENSEMBLE_ENABLED", True),
        open_meteo_weather_url=_env("OPEN_METEO_WEATHER_URL", "https://api.open-meteo.com/v1/forecast"),
        open_meteo_marine_url=_env("OPEN_METEO_MARINE_URL", "https://marine-api.open-meteo.com/v1/marine"),
        metno_weather_url=_env("METNO_WEATHER_URL", "https://api.met.no/weatherapi/locationforecast/2.0/complete"),
        metno_user_agent=_env("METNO_USER_AGENT", "ARCAFISH local app (contact: local-user)"),
        aemet_api_key=_env_optional("AEMET_API_KEY"),
        stormglass_api_key=_env_optional("STORMGLASS_API_KEY"),
        worldtides_api_key=_env_optional("WORLDTIDES_API_KEY"),
        canary_min_lat=_env_float("CANARY_MIN_LAT", 27.4),
        canary_max_lat=_env_float("CANARY_MAX_LAT", 29.6),
        canary_min_lon=_env_float("CANARY_MIN_LON", -18.6),
        canary_max_lon=_env_float("CANARY_MAX_LON", -13.2),
    )


def _load_env_file() -> None:
    path = Path(".env")
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_optional(name: str) -> str | None:
    value = os.getenv(name)
    return value or None


def _env_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, default))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _env_float(name: str, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        value = float(os.getenv(name, default))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}
