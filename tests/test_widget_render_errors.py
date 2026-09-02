import asyncio
import datetime

from extensions.epaper.core.widgets.text import TextWidget
from extensions.epaper.global_config.backend import app_config
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.screen.backend import Screen
from extensions.epaper.screen.models import ScreenModel


def _paths(tmp_path) -> EpaperPaths:
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    return paths


def _has_dark_pixel(image, x0, y0, x1, y1) -> bool:
    for x in range(x0, x1):
        for y in range(y0, y1):
            if image.getpixel((x, y)) != (255, 255, 255):
                return True
    return False


def test_a_crashing_widget_does_not_take_down_the_whole_screen(tmp_path, monkeypatch):
    """One widget raising (a bug, unexpected data, ...) must not propagate
    out of _create_image() -- unlike a datasource outage, which already
    degrades gracefully on its own, an uncaught widget exception used to
    become an unhandled 500 from the image endpoint, leaving a display with
    nothing at all instead of every *other* widget still rendering."""
    async def _boom(self, ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr(TextWidget, "draw", _boom)

    paths = _paths(tmp_path)
    config = ScreenModel(width=200, height=100, widgets=[
        {"widget_type": "Text", "position_x": 10, "position_y": 10,
         "size_width": 80, "size_height": 30, "text": "crashes"},
        {"widget_type": "Box", "position_x": 10, "position_y": 60,
         "size_width": 80, "size_height": 30, "line_width": 4},
    ])
    screen = Screen("crash-test", config, datetime.datetime.now(datetime.timezone.utc), paths)

    # must not raise
    _next_update, image = asyncio.run(screen._create_image())

    # the Box widget (untouched by the monkeypatch) still drew its border
    assert _has_dark_pixel(image, 10, 60, 90, 90)
    # the crashed Text widget's box shows the configured error text instead
    # of being blank or crashing the whole render
    assert _has_dark_pixel(image, 10, 10, 90, 40)


def test_crashing_widget_error_text_is_configurable(tmp_path, monkeypatch):
    async def _boom(self, ctx):
        raise ValueError("nope")

    monkeypatch.setattr(TextWidget, "draw", _boom)
    monkeypatch.setattr(app_config, "widget_error", "Kaputt")

    paths = _paths(tmp_path)
    config = ScreenModel(width=200, height=100, widgets=[
        {"widget_type": "Text", "position_x": 0, "position_y": 0,
         "size_width": 200, "size_height": 100, "text": "crashes"},
    ])
    screen = Screen("crash-test-2", config, datetime.datetime.now(datetime.timezone.utc), paths)
    _next_update, image = asyncio.run(screen._create_image())

    assert _has_dark_pixel(image, 0, 0, 200, 100)
