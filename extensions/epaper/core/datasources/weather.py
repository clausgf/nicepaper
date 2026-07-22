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

# WMO weather interpretation codes -> (day icon, night icon), per
# https://open-meteo.com/en/docs. Icons are language-independent; the
# human-readable descriptions live in WMO_DESCRIPTIONS below, keyed by
# language so the widget text follows the configured locale.
WMO_ICONS: dict[int, tuple[str, str]] = {
    0: (_SUN, _MOON),
    1: (_CLOUD_SUN, _CLOUD_MOON),
    2: (_CLOUD_SUN, _CLOUD_MOON),
    3: (_CLOUD, _CLOUD),
    45: (_SMOG, _SMOG),
    48: (_SMOG, _SMOG),
    51: (_CLOUD_RAIN, _CLOUD_RAIN),
    53: (_CLOUD_RAIN, _CLOUD_RAIN),
    55: (_CLOUD_RAIN, _CLOUD_RAIN),
    56: (_ICICLES, _ICICLES),
    57: (_ICICLES, _ICICLES),
    61: (_CLOUD_SUN_RAIN, _CLOUD_MOON_RAIN),
    63: (_CLOUD_RAIN, _CLOUD_RAIN),
    65: (_CLOUD_SHOWERS_HEAVY, _CLOUD_SHOWERS_HEAVY),
    66: (_ICICLES, _ICICLES),
    67: (_ICICLES, _ICICLES),
    71: (_SNOWFLAKE, _SNOWFLAKE),
    73: (_SNOWFLAKE, _SNOWFLAKE),
    75: (_SNOWFLAKE, _SNOWFLAKE),
    77: (_SNOWFLAKE, _SNOWFLAKE),
    80: (_CLOUD_SUN_RAIN, _CLOUD_MOON_RAIN),
    81: (_CLOUD_SHOWERS_HEAVY, _CLOUD_SHOWERS_HEAVY),
    82: (_CLOUD_SHOWERS_HEAVY, _CLOUD_SHOWERS_HEAVY),
    85: (_SNOWFLAKE, _SNOWFLAKE),
    86: (_SNOWFLAKE, _SNOWFLAKE),
    95: (_CLOUD_BOLT, _CLOUD_BOLT),
    96: (_CLOUD_BOLT, _CLOUD_BOLT),
    99: (_CLOUD_BOLT, _CLOUD_BOLT),
}
_UNKNOWN_ICON = (_CLOUD, _CLOUD)

# Per-language WMO descriptions. The language is derived from app_config.locale
# (e.g. "de_DE.utf8" -> "de"); unknown locales fall back to English.
WMO_DESCRIPTIONS: dict[str, dict[int, str]] = {
    "de": {
        0: "Klarer Himmel", 1: "Überwiegend klar", 2: "Teilweise bewölkt", 3: "Bedeckt",
        45: "Nebel", 48: "Reifnebel",
        51: "Leichter Nieselregen", 53: "Nieselregen", 55: "Starker Nieselregen",
        56: "Leichter gefrierender Nieselregen", 57: "Gefrierender Nieselregen",
        61: "Leichter Regen", 63: "Regen", 65: "Starker Regen",
        66: "Leichter gefrierender Regen", 67: "Gefrierender Regen",
        71: "Leichter Schneefall", 73: "Schneefall", 75: "Starker Schneefall", 77: "Schneegriesel",
        80: "Leichte Regenschauer", 81: "Regenschauer", 82: "Heftige Regenschauer",
        85: "Leichte Schneeschauer", 86: "Schneeschauer",
        95: "Gewitter", 96: "Gewitter mit leichtem Hagel", 99: "Gewitter mit starkem Hagel",
    },
    "en": {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
        56: "Light freezing drizzle", 57: "Freezing drizzle",
        61: "Light rain", 63: "Rain", 65: "Heavy rain",
        66: "Light freezing rain", 67: "Freezing rain",
        71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
        80: "Light rain showers", 81: "Rain showers", 82: "Violent rain showers",
        85: "Light snow showers", 86: "Snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with light hail", 99: "Thunderstorm with heavy hail",
    },
}
_UNKNOWN_DESCRIPTION = {"de": "Unbekannt", "en": "Unknown"}

# 8-point compass abbreviations (index = bearing // 45, N=0 clockwise) and the
# fixed wind labels, both per language so the whole WeatherNow line follows the
# locale rather than mixing e.g. an English description with German "Böen".
_COMPASS_POINTS = {
    "de": ("N", "NO", "O", "SO", "S", "SW", "W", "NW"),
    "en": ("N", "NE", "E", "SE", "S", "SW", "W", "NW"),
}
_WIND_LABELS = {
    "de": {"wind": "Wind", "gusts": "Böen"},
    "en": {"wind": "Wind", "gusts": "Gusts"},
}

_DEFAULT_LANGUAGE = "en"


def weather_language() -> str:
    """The language key (a key of WMO_DESCRIPTIONS) derived from the first two
    letters of app_config.locale, falling back to English for locales we don't
    ship a translation for."""
    lang = app_config.locale[:2].lower()
    return lang if lang in WMO_DESCRIPTIONS else _DEFAULT_LANGUAGE


def weather_icon_and_description(weather_code: int, is_day: bool) -> tuple[str, str]:
    """(icon glyph, localized description) for a WMO weather_code, resolving
    the day/night icon variant via is_day and the language via the locale."""
    day_icon, night_icon = WMO_ICONS.get(weather_code, _UNKNOWN_ICON)
    lang = weather_language()
    description = WMO_DESCRIPTIONS[lang].get(weather_code, _UNKNOWN_DESCRIPTION[lang])
    return (day_icon if is_day else night_icon), description


def wind_direction_label(degrees: float) -> str:
    """Localized 8-point compass abbreviation for a meteorological wind bearing
    (degrees the wind blows *from*, 0 = N, clockwise)."""
    return _COMPASS_POINTS[weather_language()][round(degrees / 45) % 8]


def wind_labels() -> dict[str, str]:
    """Localized fixed labels ({"wind", "gusts"}) for the WeatherNow widget."""
    return _WIND_LABELS[weather_language()]


# Open-Meteo always delivers wind speed in km/h (we don't send a
# wind_speed_unit param), so a single cached response can be reformatted into
# whatever unit GlobalConfig.wind_speed_unit selects without refetching. Each
# entry is (display suffix, divisor to apply to the km/h value).
WIND_SPEED_UNITS: dict[str, tuple[str, float]] = {
    "kmh": ("km/h", 1.0),
    "ms": ("m/s", 3.6),
    "mph": ("mph", 1.609344),
    "kn": ("kn", 1.852),
}


def convert_wind_speed(kmh: float) -> float:
    """Convert a km/h wind speed to GlobalConfig.wind_speed_unit's numeric
    value (unknown units fall back to km/h). Used both for the WeatherNow
    label and the WeatherChart 'wind' series."""
    _, divisor = WIND_SPEED_UNITS.get(app_config.wind_speed_unit, WIND_SPEED_UNITS["kmh"])
    return kmh / divisor


def wind_speed_unit_suffix() -> str:
    """Display suffix (e.g. 'km/h', 'kn') for the configured wind speed unit."""
    suffix, _ = WIND_SPEED_UNITS.get(app_config.wind_speed_unit, WIND_SPEED_UNITS["kmh"])
    return suffix


def format_wind_speed(kmh: float) -> tuple[str, str]:
    """(rounded value string, unit suffix) for a km/h wind speed, converted to
    GlobalConfig.wind_speed_unit. Unknown units fall back to km/h."""
    return f"{convert_wind_speed(kmh):.0f}", wind_speed_unit_suffix()


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
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,is_day,wind_speed_10m,wind_direction_10m,wind_gusts_10m,surface_pressure",
        "hourly": "temperature_2m,precipitation,relative_humidity_2m,surface_pressure,wind_speed_10m,weather_code,is_day",
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
