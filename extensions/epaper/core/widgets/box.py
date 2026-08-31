from extensions.epaper.screen.models import BoxWidgetModel
from extensions.epaper.util import logger
from ..drawingcontext import DrawingContext
from .base import Widget


class BoxWidget(Widget):
    """A rectangle. Does not call Widget.draw() -- its square fill/outline
    would fight a rounded corner_radius, which needs the fill and the
    outline to follow the same rounded path in one shape instead."""

    def __init__(self, id: str, config: BoxWidgetModel):
        super().__init__(id, config)

    async def draw(self, ctx: DrawingContext):
        logger.debug(f"Drawing widget type {self.config.widget_type}::{self.id}@{self.config.position}s{self.config.size}")
        if not self.config.size:
            if ctx.force_bounding_box:
                ctx.draw_origin_marker()
            return

        w, h = self.config.size
        x0, y0 = ctx.origin
        box = [x0, y0, x0 + w - 1, y0 + h - 1]
        fill = ctx.color_background if self.config.init_background else None
        outline = ctx.color_primary if self.config.line_width > 0 else None
        if self.config.corner_radius:
            ctx.draw.rounded_rectangle(box, radius=self.config.corner_radius, fill=fill,
                                       outline=outline, width=self.config.line_width)
        else:
            ctx.draw.rectangle(box, fill=fill, outline=outline, width=self.config.line_width)
        if ctx.force_bounding_box:
            ctx.draw.rectangle(box, outline=ctx.color_primary)
