import asyncio
import datetime
import json
from zoneinfo import ZoneInfo

from extensions.epaper.config import app_config
from extensions.epaper.core.datasources.weather import WMO_CODES, get_weather, weather_icon_and_description


def test_wmo_codes_have_day_and_night_icons():
    for code, (day_icon, night_icon, description) in WMO_CODES.items():
        assert day_icon, f"missing day icon for code {code}"
        assert night_icon, f"missing night icon for code {code}"
        assert description


def test_weather_icon_and_description_resolves_day_and_night():
    day_icon, description = weather_icon_and_description(0, True)
    night_icon, _ = weather_icon_and_description(0, False)
    assert day_icon != night_icon
    assert description == "Klarer Himmel"


def test_weather_icon_and_description_unknown_code_falls_back():
    icon, description = weather_icon_and_description(-1, True)
    assert icon
    assert description == "Unbekannt"


def test_get_weather_uses_cache_without_network_call(tmp_path):
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    cache_file = tmp_path / "52.5200_13.4050.json"
    cached_payload = {"current": {"temperature_2m": 21.5}, "hourly": {"time": []}}
    cache_file.write_text(json.dumps({
        "last_update": now.isoformat(),
        "data": cached_payload,
    }))

    result = asyncio.run(get_weather(tmp_path, 52.52, 13.405))
    assert result == cached_payload
