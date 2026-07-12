from typing import Optional, Tuple, List, Literal
from pydantic import BaseModel

from extensions.epaper.core.drawingcontext import DrawingContext
from extensions.epaper.models.screenmodel import WidgetModel
from extensions.epaper.util import logger


class Widget:
    """
    Base class for all widget types:
    - widgets are drawn on a DrawingContext
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

        ctx.origin = self.config.position
        if self.config.init_background and self.config.size:
            p0 = self.config.position
            p1 = tuple(sum(x)-1 for x in zip(self.config.position, self.config.size))
            ctx.draw.rectangle([p0, p1], fill=ctx.color_background)
            #ctx.draw.rectangle([p0, p1], outline=(255,0,0))
        if self.config.font:
            self.font = ctx.get_font(self.config.font[0], self.config.font[1])
        else:
            self.font = ctx.font
