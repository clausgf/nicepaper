import hashlib
from typing import Literal, Optional
from zoneinfo import ZoneInfo
from pydantic import Field
import datetime
from babel.dates import format_datetime, get_timezone

from extensions.epaper.config import app_config
from extensions.epaper.models.screenmodel import RoomCalendarWidgetModel
from extensions.epaper.core.datasources.ical import get_from_ical
from extensions.epaper.util import logger
from ..drawingcontext import DrawingContext
from .base import Widget


class RoomCalendarWidget(Widget):

    def __init__(self, id: str, config: RoomCalendarWidgetModel):
        super().__init__(id, config)
        long_id = f"RoomCalendarWidget {self.config.room_number} {self.config.room_name} {self.config.ical_url}"
        self.id = self.config.room_number + "-" + self.config.room_name + "-" + hashlib.sha256(long_id.encode()).hexdigest()[:8]
        if not self.config.size:
            self.config.size = (600,400)
            logger.info(f"Widget {self.id} has no size, assuming {self.config.size}")
        self.date_format_long = self.config.date_format_long or app_config.roomcalendar_date_format_long
        self.date_format = self.config.date_format or app_config.roomcalendar_date_format_short
        self.time_format = self.config.time_format or app_config.roomcalendar_time_format


    def draw_card(self, ctx: DrawingContext, item: dict, x: int, y: int, w: int, h: int):
        # draw rectangle around card
        p1 = (x, y)
        p2 = (x + w, y + h)
        ctx.origin = p1
        ctx.draw.rounded_rectangle([p1, p2], radius=5, outline=ctx.color_primary, width=1)

        font_title = ctx.get_font("Ubuntu-Regular.ttf", 24)
        font_default = ctx.get_font("Ubuntu-Bold.ttf", 16)
        font_awesome = ctx.get_font("fa-solid-900.ttf", 16)

        timezone = get_timezone(app_config.timezone)
        dtstart = datetime.datetime.fromisoformat(item['dtstart'])
        dtend = datetime.datetime.fromisoformat(item['dtend'])
        date = format_datetime(dtstart, format=self.date_format, tzinfo=timezone, locale=app_config.locale)
        start = format_datetime(dtstart, format=self.time_format, tzinfo=timezone, locale=app_config.locale)
        end = format_datetime(dtend, format=self.time_format, tzinfo=timezone, locale=app_config.locale)

        size = (w - 2*5, 30)
        # \uf073 = calendar, \uf007 = user, \uf017 = clock
        ctx.draw_text(position=(5,7), size=size, text=f"{item['summary']}", font=font_title, ellipsis='...')
        ctx.draw_text(position=(5,40), size=size, text=f"     {item['organizer']}", font=font_default, ellipsis='...')
        ctx.draw_text(position=(5,40), size=size, text="\uf007", font=font_awesome)
        ctx.draw_text(position=(5,65), size=size, text=f"     {date} {start}-{end}", font=font_default, ellipsis='...')
        ctx.draw_text(position=(5,65), size=size, text="\uf017", font=font_awesome)

        ctx.origin = (0,0)


    async def draw(self, ctx: DrawingContext) -> datetime.datetime:
        await super().draw(ctx)
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))
        events = await get_from_ical(ctx.paths.ical_dir, ctx.paths.organizer_names_file,
                                      self.id, self.config.ical_url, extract_organizer_from_summary=True)
        next_change = None

        x_inset = 10
        y_inset = 10
        w = self.config.size[0] // 2 - 2*x_inset
        h = self.config.size[1]
        h_card = 90
        h_card_gap = 12
        #ctx.draw.line([(self.config.size[0]//2,0), (self.config.size[0]//2,self.config.size[1])], fill=ctx.color_primary, width=1)

        # draw title
        font_room_number = ctx.get_font("Ubuntu-Regular.ttf", 144)
        ctx.draw_text((0,0), size=(w,160), text=self.config.room_number, font=font_room_number)
        font_room_name = ctx.get_font("Ubuntu-Regular.ttf", 36)
        ctx.draw_text((10,160), size=(w,40), text=self.config.room_name, font=font_room_name)
        font_date = ctx.get_font("Ubuntu-Italic.ttf", 16)
        ctx.draw_text((10,205), size=(w,40), text=format_datetime(now, format=self.date_format_long, tzinfo=ZoneInfo(app_config.timezone), locale=app_config.locale), font=font_date)

        font_default = ctx.get_font("Ubuntu-Regular.ttf", 24)
        if len(events) == 0:
            ctx.draw_text((10, h-10-h_card-8-24), size=(w, 40), text=app_config.no_appointments, font=font_default)
            return next_change

        y_card = h - 10 - h_card
        if datetime.datetime.fromisoformat(events[0]["dtstart"]) > now:
            ctx.draw_text((10, y_card-8-24), size=(w, 40), text=app_config.next_appointment, font=font_default)
            next_change = datetime.datetime.fromisoformat(events[0]["dtstart"])
        else:
            ctx.draw_text((10, y_card-8-24), size=(w, 40), text=app_config.current_appointment, font=font_default)
            next_change = datetime.datetime.fromisoformat(events[0]["dtend"])
        self.draw_card(ctx, events[0], 10, y_card, w, h_card)

        x_card = self.config.size[0] // 2 + x_inset
        dy_card = h_card + h_card_gap
        max_num_cards = (h - 2*y_inset - 8 - 24) // dy_card
        y_card = h - y_inset - max_num_cards * dy_card + h_card_gap
        if len(events) > 1:
            ctx.draw_text((x_card, y_card - 8 - 24), size=(w, 40), text=app_config.further_appointments, font=font_default)
            for event in events[1:1+max_num_cards]:
                self.draw_card(ctx, event, x_card, y_card, w, h_card)
                y_card += dy_card

        return next_change
