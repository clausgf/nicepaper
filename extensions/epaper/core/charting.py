"""
Small hand-rolled chart primitive for e-paper: a combined bar/line chart
with up to two independent Y axes, drawn directly with PIL's ImageDraw
(via DrawingContext) -- no charting library.

Widgets always draw once onto one RGB canvas; quantization to the
requested color_model's palette happens afterwards in imagecache.py
(Image.quantize(), dithered by default). Anti-aliased output (like a
typical plotting library produces) would dither into visual noise once
quantized down to a 2-3 color palette, so this helper snaps every
coordinate to an int and never anti-aliases.

Color handling: axes/gridlines/labels use ctx.color_primary (black, an
exact member of every configured palette). The primary-axis series uses
app_config.color_accent (pure red by default) -- the only accent bwr has
besides black/white, and an exact palette member of c7/e6 too, so it never
dithers regardless of which color_model was requested. The secondary-axis
series is drawn dashed in ctx.color_primary instead of a second color,
since bw/bwr can't tell two accent colors apart -- line style stays the
primary signal, color is a bonus on richer palettes.

Y-axis gridlines/labels use "nice" round numbers (Heckbert's classic
algorithm), not raw data min/max, so labels read as round figures instead
of odd fractional values.
"""
import math
from dataclasses import dataclass
from typing import Literal, Optional, Sequence

from extensions.epaper.config import app_config

Axis = Literal['primary', 'secondary']
Kind = Literal['bar', 'line']


@dataclass
class ChartSeries:
    values: Sequence[float]
    kind: Kind = 'line'
    axis: Axis = 'primary'


def _abs_pt(ctx, x: float, y: float) -> tuple[int, int]:
    return (int(ctx.origin[0] + x), int(ctx.origin[1] + y))


def _draw_dotted_hline(ctx, x0: float, x1: float, y: float, fill, dash: int = 2, gap: int = 3) -> None:
    x = x0
    while x < x1:
        seg_end = min(x + dash, x1)
        ctx.draw.line([_abs_pt(ctx, x, y), _abs_pt(ctx, seg_end, y)], fill=fill, width=1)
        x += dash + gap


def _draw_polyline(ctx, points: list[tuple[float, float]], fill, width: int, dashed: bool,
                    dash: int = 5, gap: int = 4) -> None:
    if not dashed:
        ctx.draw.line([_abs_pt(ctx, x, y) for x, y in points], fill=fill, width=width)
        return
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        if length == 0:
            continue
        step = dash + gap
        n_dashes = max(1, int(length / step) + 1)
        for i in range(n_dashes):
            t0 = min(i * step / length, 1.0)
            t1 = min(t0 + dash / length, 1.0)
            if t0 >= 1.0:
                break
            p0 = (x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0)
            p1 = (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)
            ctx.draw.line([_abs_pt(ctx, *p0), _abs_pt(ctx, *p1)], fill=fill, width=width)


def x_label_step(count: int, width: float, min_label_width: int = 40) -> int:
    """How many data points to skip between x-axis labels so they don't
    overlap -- shared with WeatherForecastWidget's hour labels."""
    max_labels = max(1, int(width // min_label_width))
    return max(1, math.ceil(count / max_labels))


def _nice_number(value: float, round_up: bool) -> float:
    """Heckbert's "nice numbers for graph labels": round `value` to 1, 2,
    5 or 10 times a power of ten, so axis steps/bounds come out as round
    figures instead of odd fractions."""
    if value <= 0:
        return 0
    exponent = math.floor(math.log10(value))
    fraction = value / 10 ** exponent
    if round_up:
        nice_fraction = 1 if fraction <= 1 else 2 if fraction <= 2 else 5 if fraction <= 5 else 10
    else:
        nice_fraction = 1 if fraction < 1.5 else 2 if fraction < 3 else 5 if fraction < 7 else 10
    return nice_fraction * 10 ** exponent


def nice_axis_range(data_min: float, data_max: float, num_ticks: int = 4) -> tuple[float, float, float]:
    """(nice_min, nice_max, nice_step) covering [data_min, data_max] with
    ~num_ticks round, human-friendly gridline steps."""
    if data_min == data_max:
        data_min, data_max = data_min - 1, data_max + 1
    step = _nice_number((data_max - data_min) / max(num_ticks - 1, 1), round_up=True)
    if step == 0:
        step = 1
    nice_min = math.floor(data_min / step) * step
    nice_max = math.ceil(data_max / step) * step
    return nice_min, nice_max, step


def _format_axis_value(value: float) -> str:
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return f'{value:.1f}'


LABEL_FONT = ("Ubuntu-Regular.ttf", 10)
LABEL_HEIGHT = 14
AXIS_LABEL_WIDTH = 26


def draw_chart(ctx, position: tuple[int, int], size: tuple[int, int], series: Sequence[ChartSeries], *,
               labels: Optional[Sequence[str]] = None) -> None:
    """
    Draws all `series` (each 'bar' or 'line', on the 'primary' or
    'secondary' Y axis) sharing one X axis (data point index). At most one
    axis label pair (min at the bottom, max at the top, nice round
    numbers) is drawn per side: primary on the left, secondary on the
    right if any secondary series is present.
    """
    x0, y0 = position
    w, h = size
    n = max((len(s.values) for s in series), default=0)
    if not series or n == 0 or w <= 0 or h <= 0:
        return

    has_secondary = any(s.axis == 'secondary' for s in series)
    left_margin = AXIS_LABEL_WIDTH
    right_margin = AXIS_LABEL_WIDTH if has_secondary else 0
    label_h = LABEL_HEIGHT if labels else 0
    plot_x0 = x0 + left_margin
    plot_w = w - left_margin - right_margin
    plot_h = h - label_h
    if plot_w <= 0 or plot_h <= 0:
        return

    def axis_range(axis: Axis) -> tuple[float, float, float]:
        axis_series = [s for s in series if s.axis == axis]
        values = [v for s in axis_series for v in s.values]
        data_min, data_max = min(values), max(values)
        if any(s.kind == 'bar' for s in axis_series):
            data_min, data_max = min(0, data_min), max(0, data_max)
            if data_min == data_max == 0:
                # e.g. no precipitation at all: a bar quantity can't go
                # negative, so don't let nice_axis_range's generic
                # equal-min-max fallback pad symmetrically into negatives
                return (0.0, 1.0, 1.0)
        return nice_axis_range(data_min, data_max)

    primary_min, primary_max, primary_step = axis_range('primary')
    secondary_min = secondary_max = secondary_step = 0.0
    if has_secondary:
        secondary_min, secondary_max, secondary_step = axis_range('secondary')

    def to_y(value: float, axis: Axis) -> float:
        nice_min, nice_max = (primary_min, primary_max) if axis == 'primary' else (secondary_min, secondary_max)
        span = max(nice_max - nice_min, 1e-6)
        return y0 + plot_h - (value - nice_min) / span * plot_h

    slot_w = plot_w / n
    def slot_center_x(i: int) -> float:
        return plot_x0 + slot_w * (i + 0.5)

    # baseline + gridlines, at the primary axis' nice steps
    ctx.draw.line([_abs_pt(ctx, plot_x0, y0 + plot_h), _abs_pt(ctx, plot_x0 + plot_w, y0 + plot_h)],
                  fill=ctx.color_primary, width=1)
    step_count = round((primary_max - primary_min) / primary_step) if primary_step else 0
    for i in range(1, step_count):
        y = to_y(primary_min + i * primary_step, 'primary')
        _draw_dotted_hline(ctx, plot_x0, plot_x0 + plot_w, y, fill=ctx.color_primary)

    # axis min/max labels
    label_font = ctx.get_font(*LABEL_FONT)
    y_bottom, y_top = to_y(primary_min, 'primary'), to_y(primary_max, 'primary')
    ctx.draw_text((x0, int(y_bottom - 6)), size=(left_margin - 2, 12), text=_format_axis_value(primary_min),
                  alignment='rc', font=label_font)
    ctx.draw_text((x0, int(y_top - 6)), size=(left_margin - 2, 12), text=_format_axis_value(primary_max),
                  alignment='rc', font=label_font)
    if has_secondary:
        right_x = plot_x0 + plot_w + 2
        ctx.draw_text((int(right_x), int(y_bottom - 6)), size=(right_margin - 2, 12),
                      text=_format_axis_value(secondary_min), alignment='lc', font=label_font)
        ctx.draw_text((int(right_x), int(y_top - 6)), size=(right_margin - 2, 12),
                      text=_format_axis_value(secondary_max), alignment='lc', font=label_font)

    accent = app_config.color_accent or ctx.color_primary
    bar_gap = 2
    for s in series:
        is_primary = s.axis == 'primary'
        color = accent if is_primary else ctx.color_primary
        if s.kind == 'bar':
            zero_y = to_y(0, s.axis)
            for i, v in enumerate(s.values):
                bx0 = plot_x0 + i * slot_w + bar_gap / 2
                bx1 = plot_x0 + (i + 1) * slot_w - bar_gap / 2
                vy = to_y(v, s.axis)
                top, bottom = (vy, zero_y) if vy < zero_y else (zero_y, vy)
                if bottom - top > 0:
                    ctx.draw.rectangle([_abs_pt(ctx, bx0, top), _abs_pt(ctx, bx1, bottom)], fill=color)
        else:
            points = [(slot_center_x(i), to_y(v, s.axis)) for i, v in enumerate(s.values)]
            _draw_polyline(ctx, points, fill=color, width=2 if is_primary else 1, dashed=not is_primary)

    if labels:
        step = x_label_step(n, plot_w)
        for i in range(0, min(n, len(labels)), step):
            px = slot_center_x(i)
            ctx.draw_text((int(px - 20), int(y0 + plot_h + 2)), size=(40, label_h), text=labels[i],
                          alignment='ct', font=label_font)
