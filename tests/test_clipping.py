import asyncio
import datetime

from extensions.epaper.core.screen import Screen
from extensions.epaper.models.screenmodel import ScreenModel
from extensions.epaper.paths import EpaperPaths

# a small box with far too much text at a large font: guaranteed to
# overflow (verified: spills all the way to the far edge of a 200px-wide
# canvas) so the tests can tell clipped from unclipped apart by pixel content
_OVERFLOWING_WIDGET = {
    "widget_type": "Text", "position_x": 10, "position_y": 10,
    "size_width": 40, "size_height": 20, "text": "VERY WIDE OVERFLOWING TEXT", "font_size": 40,
    "init_background": False,
}


def _render(tmp_path, widget_overrides: dict):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    config = ScreenModel(width=200, height=100, widgets=[{**_OVERFLOWING_WIDGET, **widget_overrides}])
    screen = Screen("clip-test", config, datetime.datetime.now(datetime.timezone.utc), paths)
    _next_update, image = asyncio.run(screen._create_image())
    return image


def _has_dark_pixel(image, x0, y0, x1, y1) -> bool:
    for x in range(x0, x1):
        for y in range(y0, y1):
            if image.getpixel((x, y)) != (255, 255, 255):
                return True
    return False


def test_without_clipping_overflow_is_visible_outside_box(tmp_path):
    image = _render(tmp_path, {"clipping": False})
    # box is x:[10,49]; the long string at font_size=40 spills well past
    # the right edge without clipping
    assert _has_dark_pixel(image, 55, 0, 200, 100)


def test_with_clipping_overflow_is_cut_off(tmp_path):
    image = _render(tmp_path, {"clipping": True})
    # same overflowing content, but nothing may appear outside the box now
    assert not _has_dark_pixel(image, 55, 0, 200, 100)


def test_show_bounding_box_draws_outline(tmp_path):
    image = _render(tmp_path, {"show_bounding_box": True, "clipping": True})
    # top edge of the box (y=10) between x=10..49 should be outlined
    assert any(image.getpixel((x, 10)) != (255, 255, 255) for x in range(10, 50))


def test_without_show_bounding_box_no_outline(tmp_path):
    image = _render(tmp_path, {"show_bounding_box": False, "clipping": False})
    # far corner of a differently-positioned box-less run: nothing drawn
    # at the box edge itself if content doesn't happen to reach it
    assert image.getpixel((10, 10)) == (255, 255, 255)
