
from extensions.epaper.core.drawingcontext import DrawingContext
from extensions.epaper.models.screenmodel import WidgetModel
from extensions.epaper.util import logger


class Widget:
    """
    Base class for all widget types:
    - widgets are drawn on a DrawingContext

    Draws relative to ctx.origin, which the caller (Screen._create_image())
    sets before calling draw() -- either the widget's absolute position on
    the shared canvas, or (0, 0) when config.clipping is set and the
    caller instead draws this widget onto an isolated, size-bounded
    sub-image that gets pasted (and thereby clipped) afterwards, see
    screen.py. Widgets never read self.config.position for drawing, only
    ctx.origin, so the same widget code works unchanged in both cases.
    """

    def __init__(self, id: str, config: WidgetModel):
        """
        Create a widget instance.
        """
        self.id = id
        self.config = config

    async def draw(self, ctx: DrawingContext):
        """
        Draw the widget using the given settings, datasource and drawing context (to which is attached an image).
        Override this method in concrete widget types to do the actual work!
        """
        logger.debug(f"Drawing widget type {self.config.widget_type}::{self.id}@{self.config.position}s{self.config.size}")

        if self.config.size:
            p0 = ctx.origin
            p1 = (ctx.origin[0] + self.config.size[0] - 1, ctx.origin[1] + self.config.size[1] - 1)
            if self.config.init_background:
                ctx.draw.rectangle([p0, p1], fill=ctx.color_background)
            if self.config.show_bounding_box:
                ctx.draw.rectangle([p0, p1], outline=ctx.color_primary)
        # each font aspect falls back to the context's default independently,
        # so overriding just the name or just the size takes effect
        font_name, font_size = self.config.resolved_font(*ctx.font_model)
        self.font = ctx.get_font(font_name, font_size)
