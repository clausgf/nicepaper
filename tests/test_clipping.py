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


def _render(tmp_path, widget_overrides: dict, boxes: bool = False):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    config = ScreenModel(width=200, height=100, widgets=[{**_OVERFLOWING_WIDGET, **widget_overrides}])
    screen = Screen("clip-test", config, datetime.datetime.now(datetime.timezone.utc), paths)
    _next_update, image = asyncio.run(screen._create_image(force_bounding_box=boxes))
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


def test_outline_toggle_draws_the_box(tmp_path):
    """The editor's outline view (force_bounding_box, ?boxes=true); there
    is no per-widget flag for it any more, so it is only ever on for a
    preview render."""
    image = _render(tmp_path, {"clipping": True}, boxes=True)
    # top edge of the box (y=10) between x=10..49 should be outlined
    assert any(image.getpixel((x, 10)) != (255, 255, 255) for x in range(10, 50))


def test_a_normal_render_has_no_outline(tmp_path):
    image = _render(tmp_path, {"clipping": True})
    # the box's top edge stays clear -- clipping keeps the text inside, and
    # nothing outlines the box itself
    assert all(image.getpixel((x, 10)) == (255, 255, 255) for x in range(10, 50))


def test_outline_toggle_marks_an_auto_sized_widget(tmp_path):
    """A widget without a size has no box to outline, so its anchor --
    the position_x/position_y being edited -- gets a corner mark."""
    image = _render(tmp_path, {"size_width": None, "size_height": None,
                               "text": "x", "font_size": 12}, boxes=True)
    assert image.getpixel((10, 10)) != (255, 255, 255), "corner mark at the anchor"
    assert image.getpixel((16, 10)) != (255, 255, 255), "horizontal arm"
    assert image.getpixel((10, 16)) != (255, 255, 255), "vertical arm"
