"""
Small hand-rolled gauge primitive for e-paper: a value on a fixed scale,
drawn either as a 240° arc or as a horizontal bar, directly with PIL's
ImageDraw (via DrawingContext) -- no charting library, for the same reasons
charting.py gives: PIL's arc/rectangle primitives are hard-edged, so the
result survives quantization to a 2-3 color palette instead of dithering
into noise the way an anti-aliased gauge image (or a screenshot of a
browser-rendered gauge) would.

Color follows the same convention as charting.py: the scale/outline/labels
use ctx.color_primary (black, an exact member of every palette), the filled
value uses ctx.color_accent (red by default, but a display preset for a
black/white panel sets it to black). On a bw display the
fill and the outline are the same color, so the *shape* has to carry the
information: the empty part of the scale stays an outline, the filled part
is solid.

Text: callers pass their widget's configured font (`font`) for the labels
plus an optional larger `value_font` for the readout; every measurement is
taken from those fonts' real metrics, so nothing is clipped at an unusual
font size.
"""
import math
from typing import Literal, Optional, Tuple

GaugeStyle = Literal['arc', 'bar']

# PIL angles: 0° is 3 o'clock and grows clockwise (y grows downward), so the
# arc starts at the lower left (150°) and sweeps 240° over the top to the
# lower right (30°) -- the classic open-bottom gauge.
ARC_START_DEG = 150.0
ARC_SWEEP_DEG = 240.0


def value_fraction(value: float, min_value: float, max_value: float) -> float:
    """Where `value` sits on the [min_value, max_value] scale, as 0.0 … 1.0.
    Values outside the scale are clamped (a gauge has no room to show them,
    and a partly-drawn-off arc would read as a wrong value)."""
    span = max_value - min_value
    if span == 0:
        return 0.0
    return min(1.0, max(0.0, (value - min_value) / span))


def _abs_pt(ctx, x: float, y: float) -> Tuple[int, int]:
    return (int(ctx.origin[0] + x), int(ctx.origin[1] + y))


def _abs_box(ctx, x0: float, y0: float, x1: float, y1: float) -> list:
    return [_abs_pt(ctx, x0, y0), _abs_pt(ctx, x1, y1)]


def _polar(cx: float, cy: float, r: float, deg: float) -> Tuple[float, float]:
    rad = math.radians(deg)
    return (cx + r * math.cos(rad), cy + r * math.sin(rad))


def _format_scale_value(value: float) -> str:
    """Compact end label for the scale: integers without a decimal point."""
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return f'{value:.1f}'


def _draw_arc(ctx, cx: float, cy: float, r: float, start: float, end: float, fill, width: int) -> None:
    """PIL arc inside the ellipse of radius r around (cx, cy); `width` grows
    inward from that radius."""
    ctx.draw.arc(_abs_box(ctx, cx - r, cy - r, cx + r, cy + r),
                 start=start, end=end, fill=fill, width=max(1, int(width)))


def _draw_arc_gauge(ctx, x0: int, y0: int, w: int, h: int, *, fraction: Optional[float],
                    font, value_font, label: Optional[str], value_text: str,
                    min_label: str, max_label: str, accent) -> None:
    row_h = ctx.textsize('Ag', font)[1] + 2
    label_h = row_h if label else 0
    arc_h = h - label_h - row_h          # row_h reserved for the min/max end labels
    r = min(w / 2, arc_h / 1.5)          # the 240° sweep is 2r wide and 1.5r high
    if r < 8:
        # too small for a readable arc -- just show the readout
        ctx.draw_text((x0, y0), size=(w, h), text=value_text, alignment='cc',
                      font=value_font, ellipsis='...')
        return

    thickness = max(5, round(r * 0.22))
    cx = x0 + w / 2
    cy = y0 + (arc_h - 1.5 * r) / 2 + r  # center the arc block in its area

    # empty scale: outer + inner outline with radial end caps, so on a bw
    # palette it still reads as "not filled" next to the solid value arc
    _draw_arc(ctx, cx, cy, r, ARC_START_DEG, ARC_START_DEG + ARC_SWEEP_DEG, ctx.color_primary, 1)
    _draw_arc(ctx, cx, cy, r - thickness, ARC_START_DEG, ARC_START_DEG + ARC_SWEEP_DEG, ctx.color_primary, 1)
    for deg in (ARC_START_DEG, ARC_START_DEG + ARC_SWEEP_DEG):
        ctx.draw.line([_abs_pt(ctx, *_polar(cx, cy, r - thickness, deg)),
                       _abs_pt(ctx, *_polar(cx, cy, r, deg))], fill=ctx.color_primary, width=1)

    # filled part, inset by 1px so it sits inside the outline instead of on it
    if fraction:
        _draw_arc(ctx, cx, cy, r - 1, ARC_START_DEG, ARC_START_DEG + ARC_SWEEP_DEG * fraction,
                  accent, thickness - 2)

    # readout centered in the arc's opening
    ctx.draw_text((int(cx - r * 0.8), int(cy - r * 0.35)), size=(int(r * 1.6), int(r * 0.9)),
                  text=value_text, alignment='cc', font=value_font, ellipsis='...')

    # scale ends just below the arc's open bottom, label under the whole gauge
    ends_y = int(y0 + arc_h)
    ctx.draw_text((x0, ends_y), size=(w // 2, row_h), text=min_label, alignment='lt', font=font)
    ctx.draw_text((x0 + w - w // 2, ends_y), size=(w // 2, row_h), text=max_label, alignment='rt', font=font)
    if label:
        ctx.draw_text((x0, y0 + h - label_h), size=(w, label_h), text=label,
                      alignment='ct', font=font, ellipsis='...')


def _draw_bar_gauge(ctx, x0: int, y0: int, w: int, h: int, *, fraction: Optional[float],
                    font, value_font, label: Optional[str], value_text: str,
                    min_label: str, max_label: str, accent) -> None:
    row_h = ctx.textsize('Ag', font)[1] + 2
    header_h = max(row_h, ctx.textsize('Ag', value_font)[1] + 2)
    footer_h = row_h

    # label and readout share the top row (label left, value right): denser
    # than stacking them, and the value stays next to the bar it belongs to
    if label:
        ctx.draw_text((x0, y0), size=(w // 2, header_h), text=label, alignment='lc',
                      font=font, ellipsis='...')
    ctx.draw_text((x0 + w // 2, y0), size=(w - w // 2, header_h), text=value_text,
                  alignment='rc', font=value_font, ellipsis='...')

    # the bar itself keeps a fixed, readable height and is centered in
    # whatever vertical space is left, instead of stretching with the box
    space = h - header_h - footer_h
    bar_h = max(6, min(space, round(row_h * 1.2)))
    bar_y = y0 + header_h + max(0, (space - bar_h) // 2)
    ctx.draw.rectangle(_abs_box(ctx, x0, bar_y, x0 + w - 1, bar_y + bar_h - 1),
                       outline=ctx.color_primary, width=1)
    if fraction:
        fill_w = round((w - 2) * fraction)
        if fill_w >= 1:
            ctx.draw.rectangle(_abs_box(ctx, x0 + 1, bar_y + 1, x0 + fill_w, bar_y + bar_h - 2),
                               fill=accent)

    ends_y = y0 + h - footer_h
    ctx.draw_text((x0, ends_y), size=(w // 2, footer_h), text=min_label, alignment='lb', font=font)
    ctx.draw_text((x0 + w - w // 2, ends_y), size=(w // 2, footer_h), text=max_label,
                  alignment='rb', font=font)


def draw_gauge(ctx, position: Tuple[int, int], size: Tuple[int, int], *,
               value: Optional[float], min_value: float, max_value: float,
               style: GaugeStyle = 'arc', font=None, value_font=None,
               label: Optional[str] = None, value_text: Optional[str] = None) -> None:
    """
    Draw `value` on the [min_value, max_value] scale into the given box.

    `style` picks the shape ('arc': a 240° open-bottom dial, 'bar': a
    horizontal bar). `value_text` is the readout as it should appear (already
    formatted and with its unit) -- it defaults to the plain number, and is
    also what gets drawn when `value` is None (a non-numeric state like
    'unavailable': the scale is then drawn empty rather than as 0).
    `label` is drawn below the arc / next to the bar readout; None omits it.
    """
    x0, y0 = position
    w, h = size
    if w <= 0 or h <= 0:
        return
    font = font or ctx.font
    value_font = value_font or font
    accent = ctx.color_accent or ctx.color_primary
    fraction = None if value is None else value_fraction(value, min_value, max_value)
    if value_text is None:
        value_text = _format_scale_value(value) if value is not None else ''

    draw = _draw_arc_gauge if style == 'arc' else _draw_bar_gauge
    draw(ctx, x0, y0, w, h, fraction=fraction, font=font, value_font=value_font,
         label=label, value_text=value_text,
         min_label=_format_scale_value(min_value), max_label=_format_scale_value(max_value),
         accent=accent)
