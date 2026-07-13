import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
import aiofiles
import aiohttp
from extensions.epaper.config import app_config
from extensions.epaper.util import logger


_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# fa-solid-900.ttf glyph codepoints (already bundled for RoomCalendarWidget's
# icons) -- verified by inspecting the font's glyph names, no new icon asset
# needed for weather icons.
_SUN = ""
_MOON = ""
_CLOUD = ""
_CLOUD_SUN = ""
_CLOUD_MOON = ""
_CLOUD_SUN_RAIN = ""
_CLOUD_MOON_RAIN = ""
_CLOUD_RAIN = ""
_CLOUD_SHOWERS_HEAVY = ""
_CLOUD_BOLT = ""
_SMOG = ""
_ICICLES = ""
_SNOWFLAKE = ""

# WMO weather interpretation codes -> (day icon, night icon, German
# description), per https://open-meteo.com/en/docs.
WMO_CODES: dict[int, tuple[str, str, str]] = {
    0: (_SUN, _MOON, "Klarer Himmel"),
    1: (_CLOUD_SUN, _CLOUD_MOON, "Überwiegend klar"),
    2: (_CLOUD_SUN, _CLOUD_MOON, "Teilweise bewölkt"),
    3: (_CLOUD, _CLOUD, "Bedeckt"),
    45: (_SMOG, _SMOG, "Nebel"),
    48: (_SMOG, _SMOG, "Reifnebel"),
    51: (_CLOUD_RAIN, _CLOUD_RAIN, "Leichter Nieselregen"),
    53: (_CLOUD_RAIN, _CLOUD_RAIN, "Nieselregen"),
    55: (_CLOUD_RAIN, _CLOUD_RAIN, "Starker Nieselregen"),
    56: (_ICICLES, _ICICLES, "Leichter gefrierender Nieselregen"),
    57: (_ICICLES, _ICICLES, "Gefrierender Nieselregen"),
    61: (_CLOUD_SUN_RAIN, _CLOUD_MOON_RAIN, "Leichter Regen"),
    63: (_CLOUD_RAIN, _CLOUD_RAIN, "Regen"),
    65: (_CLOUD_SHOWERS_HEAVY, _CLOUD_SHOWERS_HEAVY, "Starker Regen"),
    66: (_ICICLES, _ICICLES, "Leichter gefrierender Regen"),
    67: (_ICICLES, _ICICLES, "Gefrierender Regen"),
    71: (_SNOWFLAKE, _SNOWFLAKE, "Leichter Schneefall"),
    73: (_SNOWFLAKE, _SNOWFLAKE, "Schneefall"),
    75: (_SNOWFLAKE, _SNOWFLAKE, "Starker Schneefall"),
    77: (_SNOWFLAKE, _SNOWFLAKE, "Schneegriesel"),
    80: (_CLOUD_SUN_RAIN, _CLOUD_MOON_RAIN, "Leichte Regenschauer"),
    81: (_CLOUD_SHOWERS_HEAVY, _CLOUD_SHOWERS_HEAVY, "Regenschauer"),
    82: (_CLOUD_SHOWERS_HEAVY, _CLOUD_SHOWERS_HEAVY, "Heftige Regenschauer"),
    85: (_SNOWFLAKE, _SNOWFLAKE, "Leichte Schneeschauer"),
    86: (_SNOWFLAKE, _SNOWFLAKE, "Schneeschauer"),
    95: (_CLOUD_BOLT, _CLOUD_BOLT, "Gewitter"),
    96: (_CLOUD_BOLT, _CLOUD_BOLT, "Gewitter mit leichtem Hagel"),
    99: (_CLOUD_BOLT, _CLOUD_BOLT, "Gewitter mit starkem Hagel"),
}
_UNKNOWN_CODE = (_CLOUD, _CLOUD, "Unbekannt")


def weather_icon_and_description(weather_code: int, is_day: bool) -> tuple[str, str]:
    """(icon glyph, German description) for a WMO weather_code, resolving
    the day/night icon variant via is_day."""
    day_icon, night_icon, description = WMO_CODES.get(weather_code, _UNKNOWN_CODE)
    return (day_icon if is_day else night_icon), description


_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    """
    Create the shared HTTP session lazily: a ClientSession must be
    created inside a running event loop.
    """
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(raise_for_status=True)
    return _session


async def get_weather(weather_dir: Path, latitude: float, longitude: float) -> dict:
    """
    Fetch (or return cached) Open-Meteo forecast data for a location.
    Cached per rounded coordinates so multiple weather widgets at the same
    location (e.g. a "now" and a "forecast" widget) share one cached
    response instead of each fetching their own. Returns the raw Open-Meteo
    JSON response (dict with "current" and "hourly" keys); widgets read the
    fields they need directly, no intermediate model -- same approach as
    get_from_ical()'s plain event dicts.
    """
    cache_filename = os.path.join(weather_dir, f"{latitude:.4f}_{longitude:.4f}.json")

    data = None
    if os.path.exists(cache_filename):
        async with aiofiles.open(cache_filename, "r") as cache_file:
            data = json.loads(await cache_file.read())
    if data is not None and 'last_update' in data and 'data' in data:
        last_update = datetime.datetime.fromisoformat(data['last_update'])
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))
        timedelta = now - last_update
        if timedelta.total_seconds() < app_config.weather_update_interval_s:
            logger.info(f"Weather {latitude},{longitude} skipping update, last update was {timedelta.total_seconds()} seconds ago")
            return data['data']

    logger.info(f"Weather {latitude},{longitude} updating from {_BASE_URL}")
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,is_day,wind_speed_10m,wind_direction_10m,surface_pressure",
        "hourly": "temperature_2m,precipitation,relative_humidity_2m,surface_pressure,weather_code,is_day",
        "forecast_days": 2,
        "timezone": app_config.timezone,
    }
    async with _get_session().get(_BASE_URL, params=params) as response:
        forecast = await response.json()

    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    data = {
        'last_update': now.isoformat(),
        'data': forecast,
    }
    async with aiofiles.open(cache_filename, "w") as cache_file:
        await cache_file.write(json.dumps(data))

    return forecast
