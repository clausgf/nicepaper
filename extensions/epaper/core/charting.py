"""
Small hand-rolled chart primitives for e-paper: bar and line charts drawn
directly with PIL's ImageDraw (via DrawingContext), no charting library.

Widgets always draw once onto one RGB canvas; quantization to the
requested color_model's palette happens afterwards in imagecache.py
(Image.quantize(), dithered by default). Anti-aliased output (like a
typical plotting library produces) would dither into visual noise once
quantized down to a 2-3 color palette, so these helpers snap every
coordinate to an int and never anti-alias.

Color handling: axes/gridlines/labels use ctx.color_primary (black, an
exact member of every configured palette). The first data series uses
app_config.color_accent (pure red by default) -- the only accent bwr has
besides black/white, and an exact palette member of c7/e6 too, so it never
dithers regardless of which color_model was requested. Since bw/bwr can't
tell a second accent color apart from the first, additional series are
drawn dashed instead of in a different color, so they stay visually
distinguishable even when color collapses.
"""
import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

from extensions.epaper.config import app_config


@dataclass
class ChartSeries:
    values: Sequence[float]
    dashed: bool = False


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


def _x_label_step(count: int, width: float, min_label_width: int = 36) -> int:
    """How many data points to skip between x-axis labels so they don't overlap."""
    max_labels = max(1, int(width // min_label_width))
    return max(1, math.ceil(count / max_labels))


LABEL_FONT = ("Ubuntu-Regular.ttf", 10)
LABEL_HEIGHT = 14


def draw_bar_chart(ctx, position: tuple[int, int], size: tuple[int, int], values: Sequence[float], *,
                    y_max: Optional[float] = None, labels: Optional[Sequence[str]] = None) -> None:
    """Bar chart, e.g. for precipitation: mostly-zero bursty data reads
    better as solid bars than as a thin line on a bilevel display."""
    x0, y0 = position
    w, h = size
    n = len(values)
    label_h = LABEL_HEIGHT if labels else 0
    chart_h = h - label_h
    if n == 0 or w <= 0 or chart_h <= 0:
        return

    if y_max is None:
        y_max = max(values, default=0)
    y_max = max(y_max, 1e-6)

    ctx.draw.line([_abs_pt(ctx, x0, y0 + chart_h), _abs_pt(ctx, x0 + w, y0 + chart_h)],
                  fill=ctx.color_primary, width=1)
    for frac in (0.25, 0.5, 0.75):
        y = y0 + chart_h - chart_h * frac
        _draw_dotted_hline(ctx, x0, x0 + w, y, fill=ctx.color_primary)

    bar_gap = 2
    bar_w = max(1, (w - bar_gap * (n - 1)) / n)
    color = app_config.color_accent or ctx.color_primary
    label_font = ctx.get_font(*LABEL_FONT)
    for i, v in enumerate(values):
        bar_h = chart_h * min(max(v, 0) / y_max, 1.0)
        bx0 = x0 + i * (bar_w + bar_gap)
        by0 = y0 + chart_h - bar_h
        by1 = y0 + chart_h - 1
        if bar_h > 0:
            ctx.draw.rectangle([_abs_pt(ctx, bx0, by0), _abs_pt(ctx, bx0 + bar_w - 1, by1)], fill=color)
        if labels and i < len(labels):
            ctx.draw_text((int(bx0), int(y0 + chart_h + 2)), size=(int(bar_w), label_h), text=labels[i],
                          alignment='ct', font=label_font)


def draw_line_chart(ctx, position: tuple[int, int], size: tuple[int, int], series: Sequence[ChartSeries], *,
                     y_range: Optional[tuple[float, float]] = None, labels: Optional[Sequence[str]] = None) -> None:
    """Line chart, e.g. for temperature. First series solid in
    app_config.color_accent; any further series dashed in ctx.color_primary
    so they stay distinguishable even when the accent color and black
    collapse to the same value on a bilevel palette."""
    x0, y0 = position
    w, h = size
    label_h = LABEL_HEIGHT if labels else 0
    chart_h = h - label_h
    if not series or w <= 0 or chart_h <= 0:
        return
    n = max((len(s.values) for s in series), default=0)
    if n < 2:
        return

    if y_range is None:
        all_values = [v for s in series for v in s.values]
        v_min, v_max = min(all_values), max(all_values)
        if v_min == v_max:
            v_min, v_max = v_min - 1, v_max + 1
        pad = (v_max - v_min) * 0.1
        y_range = (v_min - pad, v_max + pad)
    y_min, y_max = y_range
    span = max(y_max - y_min, 1e-6)

    ctx.draw.line([_abs_pt(ctx, x0, y0 + chart_h), _abs_pt(ctx, x0 + w, y0 + chart_h)],
                  fill=ctx.color_primary, width=1)
    for frac in (0.25, 0.5, 0.75):
        y = y0 + chart_h - chart_h * frac
        _draw_dotted_hline(ctx, x0, x0 + w, y, fill=ctx.color_primary)

    def to_xy(i: int, v: float, count: int) -> tuple[float, float]:
        px = x0 + (i * (w - 1) / (count - 1) if count > 1 else 0)
        py = y0 + chart_h - (v - y_min) / span * chart_h
        return (px, py)

    accent = app_config.color_accent or ctx.color_primary
    for series_index, s in enumerate(series):
        count = len(s.values)
        if count < 2:
            continue
        points = [to_xy(i, v, count) for i, v in enumerate(s.values)]
        is_primary = series_index == 0
        color = accent if is_primary else ctx.color_primary
        _draw_polyline(ctx, points, fill=color, width=2 if is_primary else 1,
                       dashed=s.dashed or not is_primary)

    if labels:
        label_font = ctx.get_font(*LABEL_FONT)
        step = _x_label_step(n, w)
        for i in range(0, min(n, len(labels)), step):
            px, _ = to_xy(i, 0, n)
            ctx.draw_text((int(px - 20), int(y0 + chart_h + 2)), size=(40, label_h), text=labels[i],
                          alignment='ct', font=label_font)
