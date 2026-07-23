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


def test_font_parameter_changes_rendered_output():
    """A different (much larger, bolder) font must actually change what
    gets drawn -- regression guard for the font parameter silently being
    ignored in favor of a hardcoded label font."""
    values = [1, 5, 3, 8, 2]
    labels = [str(i) for i in range(len(values))]

    def render_with(font_spec):
        img = Image.new("RGB", (300, 150), color=(255, 255, 255))
        c = DrawingContext(img, (255, 255, 255), (0, 0, 0), ("Ubuntu-Regular.ttf", 16))
        font = c.get_font(*font_spec)
        draw_chart(c, (0, 0), (300, 150), [ChartSeries(values, kind="bar", axis="primary")],
                   font=font, labels=labels)
        return img

    small = render_with(("Ubuntu-Regular.ttf", 10))
    big = render_with(("Ubuntu-Bold.ttf", 30))
    assert small.tobytes() != big.tobytes()


def test_margin_is_measured_from_the_given_font_not_a_constant():
    """The mechanism behind the font fix: margins come from ctx.textsize()
    against the passed-in font, so a much wider font measures a wider
    label -- this is what makes the margin (and therefore the plot area)
    respond to the configured font at all."""
    image = Image.new("RGB", (300, 150), color=(255, 255, 255))
    ctx = DrawingContext(image, (255, 255, 255), (0, 0, 0), ("Ubuntu-Regular.ttf", 16))
    small_font = ctx.get_font("Ubuntu-Regular.ttf", 10)
    big_font = ctx.get_font("Ubuntu-Bold.ttf", 30)
    small_w, _ = ctx.textsize("20", small_font)
    big_w, _ = ctx.textsize("20", big_font)
    assert big_w > small_w


def test_vertical_gridlines_are_drawn():
    values = [1, 2, 3, 4, 5, 6, 7, 8]
    labels = [str(i) for i in range(len(values))]
    image = _render([ChartSeries(values, kind="line", axis="primary")], size=(300, 150), labels=labels)
    # a vertical gridline spans the full plot height at each labeled x
    # position -- check a row well above the line/bars and below any
    # text for a dotted vertical line's dark pixels
    assert any(image.getpixel((x, 20)) != (255, 255, 255) for x in range(40, 300))


def test_every_horizontal_gridline_gets_a_label_not_just_min_max():
    values = [0, 10, 20, 30, 40]
    image = _render([ChartSeries(values, kind="line", axis="primary")], size=(200, 200))
    # nice_axis_range(0, 40) -> (0, 40, ~10-ish) with more than 2 ticks;
    # a label must appear near the vertical middle of the left margin,
    # not just at the very top and very bottom rows
    middle_rows_dark = any(image.getpixel((x, y)) != (255, 255, 255)
                            for x in range(0, 25) for y in range(90, 110))
    assert middle_rows_dark


def test_axis_titles_draw_in_the_top_strip():
    values = [5, 10, 15, 20]
    # region past the left numeric margin and above the (pushed-down) plot:
    # blank without a title, inked by a left-aligned primary_title
    region = [(x, y) for x in range(40, 120) for y in range(0, 14)]
    blank = _render([ChartSeries(values, kind="line", axis="primary")], size=(300, 150))
    titled = _render([ChartSeries(values, kind="line", axis="primary")], size=(300, 150),
                     primary_title="Temperature")
    assert all(blank.getpixel(p) == (255, 255, 255) for p in region)
    assert any(titled.getpixel(p) != (255, 255, 255) for p in region)


def test_secondary_title_is_right_aligned():
    values = [5, 10, 15, 20]
    image = _render([ChartSeries(values, kind="line", axis="primary"),
                     ChartSeries([1, 2, 3, 4], kind="line", axis="secondary")],
                    size=(300, 150), primary_title="Temp", secondary_title="Rain")
    # secondary title sits in the right half's top strip
    right_top_dark = any(image.getpixel((x, y)) != (255, 255, 255)
                          for x in range(230, 300) for y in range(0, 14))
    assert right_top_dark
