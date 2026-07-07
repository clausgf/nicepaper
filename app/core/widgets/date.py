from typing import Literal, Optional
from pydantic import Field
from babel.dates import format_date, get_timezone
from datetime import datetime

from app.config import app_config
from app.models.screenmodel import DateWidgetModel
from app.util import logger
from ..drawingcontext import DrawingContext
from .base import Widget


class DateWidget(Widget):

    def __init__(self, id: str, config: DateWidgetModel):
        super().__init__(id, config)


    async def draw(self, ctx: DrawingContext):
        await super().draw(ctx)
        timezone = get_timezone(app_config.timezone)
        now = datetime.now(timezone)
        format = self.config.date_format or app_config.date_format
        text = format_date(now, format=format, locale=app_config.locale)

        ctx.draw_text(position=(0,0),
                        size=self.config.size, 
                        text=text, 
                        alignment=self.config.alignment,
                        font=self.font)
