from extensions.epaper.core.charting import draw_polyline
from extensions.epaper.screen.models import LineWidgetModel
from ..drawingcontext import DrawingContext
from .base import Widget


class LineWidget(Widget):

    def __init__(self, id: str, config: LineWidgetModel):
        super().__init__(id, config)

    async def draw(self, ctx: DrawingContext):
        await super().draw(ctx)
        end = (self.config.size_width or 0, self.config.size_height or 0)
        draw_polyline(ctx, [(0, 0), end], fill=ctx.color_primary,
                      width=self.config.line_width, style=self.config.line_style)
