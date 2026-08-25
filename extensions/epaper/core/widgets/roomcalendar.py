from zoneinfo import ZoneInfo
import datetime
from typing import Optional
from babel.dates import format_datetime, get_timezone
from PIL import ImageColor

from extensions.epaper.bookingsystem.backend import read_booking_system
from extensions.epaper.bookingsystem.models import BookingSystemModel
from extensions.epaper.catalog.models import Palette
from extensions.epaper.global_config.backend import app_config
from extensions.epaper.room.backend import get_room_events
from extensions.epaper.screen.models import RoomCalendarWidgetModel
from extensions.epaper.util import logger
from ..drawingcontext import DrawingContext
from .base import Widget

# Shown in place of a real room's number/name when this widget is rendered
# with no room bound (ctx.room is None) -- the Templates section's preview
# of an auto-generated "Room Calendar WxH palette" screen, or a raw screen
# id opened without device context. Keeps the preview looking like a real
# door sign instead of a blank/error box.
_PLACEHOLDER_ROOM_NUMBER = "101"
_PLACEHOLDER_ROOM_NAME = "Example Room"


_UNSUPPORTED_COLOR_FALLBACK = '#000000'


def _event_category_color(item: dict, booking_system: BookingSystemModel,
                          palette: Optional[Palette]) -> Optional[str]:
    """The drawing color for item's card: the first of its categories (see
    ical.py's `categories`, a comma-separated string per the iCal spec) that
    has a mapped color in booking_system.category_colors. The picker offers
    only the 6-color display's own colors (bookingsystem/ui.py), so on a
    panel that has that exact color it's drawn as-is; a panel that doesn't
    (e.g. bw/bwr/gs4 have no blue/green) falls back to black rather than a
    fuzzy nearest-color guess -- a booking system isn't tied to one panel, so
    there's no single "closest" that would be right for all of them. None
    (-> the caller's default color) when there is no category match at all."""
    if not booking_system.category_colors:
        return None
    for category in item['categories'].split(','):
        category = category.strip()
        if not category:
            continue
        hex_color = booking_system.category_colors.get(category)
        if hex_color is None:
            continue
        if palette is None:
            return hex_color
        return hex_color if ImageColor.getrgb(hex_color) in palette.palette else _UNSUPPORTED_COLOR_FALLBACK
    return None


class RoomCalendarWidget(Widget):

    def __init__(self, id: str, config: RoomCalendarWidgetModel):
        super().__init__(id, config)
        if not self.config.size:
            self.config.size = (600,400)
            logger.info(f"Widget {self.id} has no size, assuming {self.config.size}")
        self.date_format_long = self.config.date_format_long or app_config.roomcalendar_date_format_long
        self.date_format = self.config.date_format or app_config.roomcalendar_date_format_short
        self.time_format = self.config.time_format or app_config.roomcalendar_time_format


    def draw_card(self, ctx: DrawingContext, item: dict, x: int, y: int, w: int, h: int,
                  booking_system: Optional[BookingSystemModel]):
        # draw rectangle around card -- a category color (see
        # _event_category_color()), thicker so it reads clearly, or the
        # screen's own primary color when the event has none/isn't mapped
        color = (_event_category_color(item, booking_system, ctx.palette)
                if booking_system is not None else None)
        p1 = (x, y)
        p2 = (x + w, y + h)
        ctx.origin = p1
        ctx.draw.rounded_rectangle([p1, p2], radius=5, outline=color or ctx.color_primary,
                                   width=3 if color else 1)

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


    async def draw(self, ctx: DrawingContext) -> Optional[datetime.datetime]:
        await super().draw(ctx)
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))
        next_change = None
        room = ctx.room

        x_inset = 10
        y_inset = 10
        w = self.config.size[0] // 2 - 2*x_inset
        h = self.config.size[1]
        h_card = 90
        h_card_gap = 12
        font_default = ctx.get_font("Ubuntu-Regular.ttf", 24)

        # draw room title + date
        font_room_number = ctx.get_font("Ubuntu-Regular.ttf", 144)
        room_number = room.room_number if room is not None else _PLACEHOLDER_ROOM_NUMBER
        ctx.draw_text((0,0), size=(w,160), text=room_number, font=font_room_number)
        font_room_name = ctx.get_font("Ubuntu-Regular.ttf", 36)
        room_name = room.room_name if room is not None else _PLACEHOLDER_ROOM_NAME
        ctx.draw_text((10,160), size=(w,40), text=room_name, font=font_room_name)
        font_date = ctx.get_font("Ubuntu-Italic.ttf", 16)
        _, date_height = ctx.draw_text((10,205), size=(2*w,40),
            text=format_datetime(now, format=self.date_format_long, tzinfo=ZoneInfo(app_config.timezone), locale=app_config.locale),
            font=font_date)
        y_notes = 205 + date_height + 4

        # room notes, multiline, under the date -- only as much vertical
        # space as is left before the first appointment card would start
        notes = room.notes if room is not None else None
        if notes:
            notes_height = h - y_inset - h_card - h_card_gap - 8 - 24 - y_notes
            if notes_height > 0:
                font_notes = ctx.get_font("Ubuntu-Regular.ttf", 16)
                ctx.draw_text((10, y_notes), size=(2*w, notes_height), text=notes,
                              font=font_notes, multiline=True, ellipsis='...')

        if room is None:
            ctx.draw_text((10, h-10-h_card-8-24), size=(w, 40),
                          text="Preview — no room assigned", font=font_default)
            return next_change

        try:
            events = await get_room_events(ctx.paths, room)
        except Exception as e:
            logger.error(f"Error occurred while fetching ical data for room {room.id}: {e}")
            ctx.draw_text((10, 280), size=(w, 40), text=app_config.ical_error, font=font_default)
            return next_change

        booking_system = read_booking_system(ctx.paths, room.booking_system_id) if room.booking_system_id else None

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
        self.draw_card(ctx, events[0], 10, y_card, w, h_card, booking_system)

        x_card = self.config.size[0] // 2 + x_inset
        dy_card = h_card + h_card_gap
        max_num_cards = max(0, (h - 2*y_inset - 8 - 24) // dy_card)
        y_card = h - y_inset - max_num_cards * dy_card + h_card_gap
        if len(events) > 1 and max_num_cards > 0:
            ctx.draw_text((x_card, y_card - 8 - 24), size=(w, 40), text=app_config.further_appointments, font=font_default)
            for event in events[1:1+max_num_cards]:
                self.draw_card(ctx, event, x_card, y_card, w, h_card, booking_system)
                y_card += dy_card

        return next_change
