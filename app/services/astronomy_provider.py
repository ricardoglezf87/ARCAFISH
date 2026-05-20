from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import acos, asin, atan, cos, degrees, floor, radians, sin, tan
from zoneinfo import ZoneInfo

from app.config import Settings, get_settings


@dataclass(frozen=True)
class AstronomyInfo:
    sunrise: datetime
    sunset: datetime
    moon_phase_value: float
    moon_phase: str


class LocalAstronomyProvider:
    provider_name = "local-astral"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_days(self, latitude: float, longitude: float, dates: set[date]) -> dict[date, AstronomyInfo]:
        tz = ZoneInfo(self.settings.canary_timezone)
        result: dict[date, AstronomyInfo] = {}
        for day in dates:
            sunrise = solar_event(day, latitude, longitude, tz, sunrise=True)
            sunset = solar_event(day, latitude, longitude, tz, sunrise=False)
            phase_value = moon_age(day)
            result[day] = AstronomyInfo(
                sunrise=sunrise,
                sunset=sunset,
                moon_phase_value=phase_value,
                moon_phase=moon_phase_name(phase_value),
            )
        return result


def moon_phase_name(phase_value: float) -> str:
    if phase_value < 1.85 or phase_value >= 27.68:
        return "nueva"
    if phase_value < 5.54:
        return "creciente"
    if phase_value < 9.23:
        return "cuarto creciente"
    if phase_value < 12.92:
        return "gibosa creciente"
    if phase_value < 16.61:
        return "llena"
    if phase_value < 20.30:
        return "gibosa menguante"
    if phase_value < 23.99:
        return "cuarto menguante"
    return "menguante"


def moon_age(day: date) -> float:
    known_new_moon = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)
    synodic_month_days = 29.53058867
    return ((noon - known_new_moon).total_seconds() / 86400) % synodic_month_days


def solar_event(day: date, latitude: float, longitude: float, tz: ZoneInfo, sunrise: bool) -> datetime:
    # NOAA-style sunrise/sunset approximation. Good enough for ranking fishing windows.
    day_of_year = day.timetuple().tm_yday
    lng_hour = longitude / 15
    base_hour = 6 if sunrise else 18
    approximate_time = day_of_year + ((base_hour - lng_hour) / 24)

    mean_anomaly = (0.9856 * approximate_time) - 3.289
    true_longitude = (
        mean_anomaly
        + (1.916 * sin(radians(mean_anomaly)))
        + (0.020 * sin(radians(2 * mean_anomaly)))
        + 282.634
    ) % 360

    right_ascension = degrees(atan(0.91764 * tan(radians(true_longitude)))) % 360
    longitude_quadrant = floor(true_longitude / 90) * 90
    ascension_quadrant = floor(right_ascension / 90) * 90
    right_ascension = (right_ascension + longitude_quadrant - ascension_quadrant) / 15

    sin_declination = 0.39782 * sin(radians(true_longitude))
    cos_declination = cos(asin(sin_declination))
    zenith = radians(90.833)
    cos_hour_angle = (
        cos(zenith) - (sin_declination * sin(radians(latitude)))
    ) / (cos_declination * cos(radians(latitude)))

    if cos_hour_angle > 1 or cos_hour_angle < -1:
        fallback_hour = 7 if sunrise else 19
        return datetime(day.year, day.month, day.day, fallback_hour, tzinfo=tz)

    hour_angle = 360 - degrees(acos(cos_hour_angle)) if sunrise else degrees(acos(cos_hour_angle))
    hour_angle /= 15
    local_mean_time = hour_angle + right_ascension - (0.06571 * approximate_time) - 6.622
    universal_time = (local_mean_time - lng_hour) % 24
    hour = int(universal_time)
    minute = int((universal_time - hour) * 60)
    second = int(round((((universal_time - hour) * 60) - minute) * 60))

    event_utc = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(
        hours=hour,
        minutes=minute,
        seconds=second,
    )
    return event_utc.astimezone(tz)
