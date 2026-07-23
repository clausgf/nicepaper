import asyncio
import datetime
import json
from zoneinfo import ZoneInfo

from extensions.epaper.config import app_config
import pytest

from extensions.epaper.core.datasources.weather import (
    WMO_DESCRIPTIONS, WMO_ICONS, convert_wind_speed, format_wind_speed, get_weather,
    weather_icon_and_description, wind_direction_label, wind_labels,
)


def test_wmo_icons_have_day_and_night_variants():
    for code, (day_icon, night_icon) in WMO_ICONS.items():
        assert day_icon, f"missing day icon for code {code}"
        assert night_icon, f"missing night icon for code {code}"


def test_wmo_descriptions_cover_same_codes_in_every_language():
    codes = set(WMO_ICONS)
    for lang, table in WMO_DESCRIPTIONS.items():
        assert set(table) == codes, f"language {lang} does not cover all WMO codes"
        assert all(text for text in table.values())


def test_weather_icon_and_description_resolves_day_and_night(monkeypatch):
    monkeypatch.setattr(app_config, "locale", "de_DE.utf8")
    day_icon, description = weather_icon_and_description(0, True)
    night_icon, _ = weather_icon_and_description(0, False)
    assert day_icon != night_icon
    assert description == "Klarer Himmel"


def test_weather_description_follows_locale(monkeypatch):
    monkeypatch.setattr(app_config, "locale", "en_US.utf8")
    _, description = weather_icon_and_description(0, True)
    assert description == "Clear sky"
    assert wind_labels()["gusts"] == "Gusts"
    assert wind_direction_label(90) == "E"


def test_weather_description_unknown_locale_falls_back_to_english(monkeypatch):
    monkeypatch.setattr(app_config, "locale", "xx_XX")
    _, description = weather_icon_and_description(0, True)
    assert description == "Clear sky"


def test_weather_icon_and_description_unknown_code_falls_back(monkeypatch):
    monkeypatch.setattr(app_config, "locale", "de_DE.utf8")
    icon, description = weather_icon_and_description(-1, True)
    assert icon
    assert description == "Unbekannt"


@pytest.mark.parametrize("unit,kmh,expected", [
    ("kmh", 36.0, ("36", "km/h")),
    ("ms", 36.0, ("10", "m/s")),
    ("mph", 16.09344, ("10", "mph")),
    ("kn", 18.52, ("10", "kn")),
])
def test_format_wind_speed_converts_and_labels(monkeypatch, unit, kmh, expected):
    monkeypatch.setattr(app_config, "wind_speed_unit", unit)
    assert format_wind_speed(kmh) == expected


def test_chart_metric_maps_cover_every_weather_metric():
    from typing import get_args
    from extensions.epaper.core.datasources.weather import _METRIC_TITLES
    from extensions.epaper.core.widgets.weather import _METRIC_FIELD, _METRIC_KIND
    from extensions.epaper.models.screenmodel import WeatherMetric
    metrics = set(get_args(WeatherMetric))
    assert set(_METRIC_FIELD) == metrics
    assert set(_METRIC_KIND) == metrics
    for lang, titles in _METRIC_TITLES.items():
        assert set(titles) == metrics, f"metric titles for {lang} miss a metric"


def test_metric_title_follows_locale_and_includes_unit(monkeypatch):
    from extensions.epaper.core.datasources.weather import metric_title
    monkeypatch.setattr(app_config, "locale", "de_DE.utf8")
    assert metric_title("temperature") == "Temperatur (°C)"
    assert metric_title("precipitation") == "Niederschlag (mm)"
    monkeypatch.setattr(app_config, "locale", "en_US.utf8")
    assert metric_title("temperature") == "Temperature (°C)"


def test_metric_title_wind_unit_follows_wind_speed_unit(monkeypatch):
    from extensions.epaper.core.datasources.weather import metric_title
    monkeypatch.setattr(app_config, "locale", "en_US.utf8")
    monkeypatch.setattr(app_config, "wind_speed_unit", "kn")
    assert metric_title("wind") == "Wind (kn)"
    monkeypatch.setattr(app_config, "wind_speed_unit", "kmh")
    assert metric_title("wind") == "Wind (km/h)"


def test_convert_wind_speed_uses_configured_unit(monkeypatch):
    monkeypatch.setattr(app_config, "wind_speed_unit", "kn")
    assert round(convert_wind_speed(18.52), 2) == 10.0
    monkeypatch.setattr(app_config, "wind_speed_unit", "kmh")
    assert convert_wind_speed(36.0) == 36.0


def test_wind_direction_label_maps_bearings_to_compass(monkeypatch):
    monkeypatch.setattr(app_config, "locale", "de_DE.utf8")
    assert wind_direction_label(0) == "N"
    assert wind_direction_label(90) == "O"
    assert wind_direction_label(180) == "S"
    assert wind_direction_label(270) == "W"
    assert wind_direction_label(45) == "NO"
    # rounds to the nearest 45° sector and wraps past 360°
    assert wind_direction_label(20) == "N"
    assert wind_direction_label(340) == "N"


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
