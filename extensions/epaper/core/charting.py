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
of odd fractional values -- and every gridline gets a label, not just the
top/bottom.

Label font: callers pass their widget's own configured font (fixed size
from the Appearance card, same convention as the rest of the weather
widgets) via the `font` parameter; margins are measured from that font's
actual metrics, not a hardcoded size, so labels never get clipped by a
too-small margin at a large configured font size.
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


def _draw_dotted_vline(ctx, x: float, y0: float, y1: float, fill, dash: int = 2, gap: int = 3) -> None:
    y = y0
    while y < y1:
        seg_end = min(y + dash, y1)
        ctx.draw.line([_abs_pt(ctx, x, y), _abs_pt(ctx, x, seg_end)], fill=fill, width=1)
        y += dash + gap


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


def draw_chart(ctx, position: tuple[int, int], size: tuple[int, int], series: Sequence[ChartSeries], *,
               font=None, labels: Optional[Sequence[str]] = None,
               primary_title: Optional[str] = None, secondary_title: Optional[str] = None) -> None:
    """
    Draws all `series` (each 'bar' or 'line', on the 'primary' or
    'secondary' Y axis) sharing one X axis (data point index). Every
    horizontal gridline gets a numeric label (primary axis on the left,
    secondary on the right if any secondary series is present); vertical
    gridlines are drawn at the same X positions as the (possibly thinned)
    `labels`. `font` should be the caller's configured font (e.g. a
    widget's self.font) -- falls back to ctx.font if not given.

    `primary_title`/`secondary_title` label the two Y axes above the plot,
    left- and right-aligned respectively. They consume a strip at the top
    (so the plot gets a little shorter, not narrower), keeping the numeric
    axis labels on the sides where they are.
    """
    x0, y0 = position
    w, h = size
    n = max((len(s.values) for s in series), default=0)
    if not series or n == 0 or w <= 0 or h <= 0:
        return

    label_font = font or ctx.font

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

    has_secondary = any(s.axis == 'secondary' for s in series)
    primary_min, primary_max, primary_step = axis_range('primary')
    secondary_min = secondary_max = secondary_step = 0.0
    if has_secondary:
        secondary_min, secondary_max, secondary_step = axis_range('secondary')

    step_count = round((primary_max - primary_min) / primary_step) if primary_step else 0
    primary_labels = [_format_axis_value(primary_min + i * primary_step) for i in range(step_count + 1)]
    secondary_labels: list[str] = []
    for i in range(step_count + 1):
        frac = i / step_count if step_count else 0.0
        secondary_labels.append(_format_axis_value(secondary_min + frac * (secondary_max - secondary_min)))

    # margins measured from the actual configured font, not a fixed guess,
    # so labels never get clipped at a larger configured font size
    label_gap = 4
    row_h = ctx.textsize("0", label_font)[1] + 2
    left_margin = max(ctx.textsize(t, label_font)[0] for t in primary_labels) + label_gap
    right_margin = (max(ctx.textsize(t, label_font)[0] for t in secondary_labels) + label_gap) if has_secondary else 0
    label_h = (ctx.textsize("00:00", label_font)[1] + 4) if labels else 0
    # a strip above the plot for the axis titles (leaves plot width alone)
    title_h = (ctx.textsize("Ag", label_font)[1] + 4) if (primary_title or secondary_title) else 0

    plot_x0 = x0 + left_margin
    plot_w = w - left_margin - right_margin
    plot_y0 = y0 + title_h
    plot_h = h - label_h - title_h
    if plot_w <= 0 or plot_h <= 0:
        return

    def to_y(value: float, axis: Axis) -> float:
        nice_min, nice_max = (primary_min, primary_max) if axis == 'primary' else (secondary_min, secondary_max)
        span = max(nice_max - nice_min, 1e-6)
        return plot_y0 + plot_h - (value - nice_min) / span * plot_h

    slot_w = plot_w / n
    def slot_center_x(i: int) -> float:
        return plot_x0 + slot_w * (i + 0.5)

    x_indices = range(0, min(n, len(labels)), x_label_step(n, plot_w)) if labels else ()

    # vertical gridlines, aligned with the (thinned) x-axis labels
    for i in x_indices:
        _draw_dotted_vline(ctx, slot_center_x(i), plot_y0, plot_y0 + plot_h, fill=ctx.color_primary)

    # baseline + horizontal gridlines, each labeled on both axes in use
    ctx.draw.line([_abs_pt(ctx, plot_x0, plot_y0 + plot_h), _abs_pt(ctx, plot_x0 + plot_w, plot_y0 + plot_h)],
                  fill=ctx.color_primary, width=1)
    for i in range(step_count + 1):
        y = to_y(primary_min + i * primary_step, 'primary')
        if 0 < i < step_count:
            _draw_dotted_hline(ctx, plot_x0, plot_x0 + plot_w, y, fill=ctx.color_primary)
        # anchor top/bottom rows within [y0, y0+plot_h] instead of
        # straddling the edge; middle rows can center on their gridline
        if i == step_count:
            align_l, align_r, box_y = 'rt', 'lt', y
        elif i == 0:
            align_l, align_r, box_y = 'rb', 'lb', y - row_h
        else:
            align_l, align_r, box_y = 'rc', 'lc', y - row_h / 2
        ctx.draw_text((x0, int(box_y)), size=(left_margin - label_gap, row_h), text=primary_labels[i],
                      alignment=align_l, font=label_font)
        if has_secondary:
            right_x = plot_x0 + plot_w + 2
            ctx.draw_text((int(right_x), int(box_y)), size=(right_margin - label_gap, row_h),
                          text=secondary_labels[i], alignment=align_r, font=label_font)

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

    for i in x_indices:
        px = slot_center_x(i)
        ctx.draw_text((int(px - 20), int(plot_y0 + plot_h + 2)), size=(40, label_h), text=labels[i],
                      alignment='ct', font=label_font)

    # axis titles in the reserved top strip: primary left-aligned (accent,
    # matching its series), secondary right-aligned. Each gets half the
    # width with an ellipsis so long titles can't overlap in the middle.
    if title_h:
        half = w // 2
        if primary_title:
            ctx.draw_text((x0, y0), size=(half, title_h), text=primary_title,
                          alignment='lt', font=label_font, color=accent, ellipsis='...')
        if secondary_title:
            ctx.draw_text((x0 + w - half, y0), size=(half, title_h), text=secondary_title,
                          alignment='rt', font=label_font, ellipsis='...')
