from PIL import Image

from extensions.epaper.config import app_config
from extensions.epaper.core.drawingcontext import DrawingContext
from extensions.epaper.core.gauge import draw_gauge, value_fraction


# the gauge fill takes its color from the drawing context (a screen or a
# widget can override it), so the context under test has to carry one
_ACCENT = tuple(int(app_config.color_accent.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))


def _render(size=(160, 130), **kwargs):
    image = Image.new("RGB", size, color=(255, 255, 255))
    ctx = DrawingContext(image, (255, 255, 255), (0, 0, 0), ("Ubuntu-Regular.ttf", 14),
                         color_accent=_ACCENT)
    draw_gauge(ctx, (0, 0), size, **kwargs)
    return image


def _ink(image) -> int:
    w, h = image.size
    return sum(1 for x in range(w) for y in range(h) if image.getpixel((x, y)) != (255, 255, 255))


def _accent_pixels(image) -> int:
    w, h = image.size
    return sum(1 for x in range(w) for y in range(h) if image.getpixel((x, y)) == _ACCENT)


def test_value_fraction_maps_and_clamps():
    assert value_fraction(50, 0, 100) == 0.5
    assert value_fraction(0, 0, 100) == 0.0
    assert value_fraction(-20, 0, 100) == 0.0    # below the scale -> clamped
    assert value_fraction(300, 0, 100) == 1.0    # above the scale -> clamped
    assert value_fraction(0, -20, 20) == 0.5     # scale may start negative
    assert value_fraction(5, 10, 10) == 0.0      # degenerate scale, no crash


def test_arc_gauge_fill_grows_with_the_value():
    low = _render(value=10, min_value=0, max_value=100, style='arc', value_text='')
    high = _render(value=90, min_value=0, max_value=100, style='arc', value_text='')
    assert _accent_pixels(high) > _accent_pixels(low) > 0


def test_bar_gauge_fill_grows_with_the_value():
    low = _render(size=(200, 70), value=10, min_value=0, max_value=100, style='bar', value_text='')
    high = _render(size=(200, 70), value=90, min_value=0, max_value=100, style='bar', value_text='')
    assert _accent_pixels(high) > _accent_pixels(low) > 0


def test_non_numeric_value_draws_the_scale_empty_but_keeps_the_readout():
    """A state like 'unavailable' has no place on the scale: nothing is
    filled (which would read as the minimum), the text still shows."""
    for style, size in (('arc', (160, 130)), ('bar', (200, 70))):
        empty = _render(size=size, value=None, min_value=0, max_value=100,
                        style=style, value_text='unavailable')
        assert _accent_pixels(empty) == 0
        assert _ink(empty) > 0


def test_label_is_drawn_only_when_given():
    # the label gets its own centered row at the bottom; without one that row
    # holds only the scale ends, which sit at the left and right edges
    center = [(x, y) for x in range(60, 100) for y in range(116, 130)]
    without = _render(value=50, min_value=0, max_value=100, label=None, value_text='50')
    with_label = _render(value=50, min_value=0, max_value=100, label='Living room', value_text='50')
    assert all(without.getpixel(p) == (255, 255, 255) for p in center)
    assert any(with_label.getpixel(p) != (255, 255, 255) for p in center)


def test_gauge_stays_inside_its_box():
    """Everything must be drawn within the given box -- a gauge sits next to
    other widgets on a shared canvas, and a clipping widget would cut it."""
    size = (160, 130)
    image = Image.new("RGB", (size[0] + 20, size[1] + 20), color=(255, 255, 255))
    ctx = DrawingContext(image, (255, 255, 255), (0, 0, 0), ("Ubuntu-Regular.ttf", 14))
    draw_gauge(ctx, (0, 0), size, value=88, min_value=0, max_value=100,
               label='Living room temperature', value_text='88.0 °C')
    margin = [(x, y) for x in range(image.width) for y in range(image.height)
              if x >= size[0] or y >= size[1]]
    assert all(image.getpixel(p) == (255, 255, 255) for p in margin)


def test_tiny_box_falls_back_to_the_readout_without_crashing():
    image = _render(size=(30, 20), value=50, min_value=0, max_value=100, value_text='50')
    assert _ink(image) > 0
