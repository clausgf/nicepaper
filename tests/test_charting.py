from PIL import Image

from extensions.epaper.core.charting import ChartSeries, draw_chart, nice_axis_range
from extensions.epaper.core.drawingcontext import DrawingContext


def _render(series, size=(200, 100), **kwargs):
    image = Image.new("RGB", size, color=(255, 255, 255))
    ctx = DrawingContext(image, (255, 255, 255), (0, 0, 0), ("Ubuntu-Regular.ttf", 16))
    draw_chart(ctx, (0, 0), size, series, **kwargs)
    return image


def test_nice_axis_range_handles_negative_values():
    nice_min, nice_max, step = nice_axis_range(-15, 5)
    assert nice_min <= -15
    assert nice_max >= 5
    assert step > 0


def test_negative_and_positive_values_render_without_crashing():
    values = [-9, -5, -1, 3, 8, 12, 8, 3, -1, -5]
    image = _render([ChartSeries(values, kind="line", axis="primary")],
                     labels=[str(i) for i in range(len(values))])
    # some content must actually have been drawn (not a blank canvas)
    assert any(image.getpixel((x, y)) != (255, 255, 255) for x in range(200) for y in range(100))


def test_axis_labels_stay_within_chart_bounds():
    """Regression test: axis min/max labels were originally vertically
    centered on the min/max gridline, so the top label's box straddled
    the chart's own top edge -- half of it landed above y=0, which would
    be clipped outright by a clipping=True widget and could overlap
    whatever is drawn above it otherwise."""
    values = [-9, -5, -1, 3, 8, 12, 8, 3, -1, -5]
    image = _render([ChartSeries(values, kind="line", axis="primary")], size=(200, 100))
    # nothing should be drawn in row y=0..1: the top label's box now
    # starts exactly at the chart's own top edge (a couple of pixels of
    # font ascent margin), not straddling above it
    top_rows_dark = any(image.getpixel((x, y)) != (255, 255, 255)
                         for x in range(30) for y in (0, 1))
    assert not top_rows_dark
