"""
Room model: a room's identity and its booking source.

A room carries only its master data and which booking system feeds it. 
It deliberately does *not* carry any rendering settings. Nor does it 
list the displays in the room -- that
is a device->room relation stored in the device bindings
(devicebinding/models.py), keyed by nice4iot device name, so a room never
holds a device id that a deleted device could leave dangling.

**Identity & storage.** A room has a stable surrogate `id`, generated once at
creation and never changed. The room is stored as `<id>.json`.
"""
from typing import Annotated, Literal, Optional
from uuid import uuid4

import niceview
from pydantic import BaseModel, Field, field_validator

from extensions.epaper.bookingsystem.models import BookingSystemModel

RoomType = Literal["meeting", "conference", "lecture", "seminar", "office", "lab", "other"]

# Labels for RoomType (stored as the ids above). Kept with the model so both
# the form (room_type's FieldInfo) and the room list read the same names.
ROOM_TYPE_LABELS: dict[str, str] = {
    "meeting": "Meeting room",
    "conference": "Conference room",
    "lecture": "Lecture hall",
    "seminar": "Seminar room",
    "office": "Office",
    "lab": "Lab",
    "other": "Other",
}


class RoomModel(BaseModel):
    # --- Identity / master data -------------------------------------------
    id: Annotated[str,
            Field(default_factory=lambda: uuid4().hex,
                  description='Stable surrogate id: generated once, never changed, and also the '
                              "room's file name. It is what device bindings reference, so a room "
                              'can be renamed freely.'),
            niceview.Field(editable=False, hidden=True)
        ]

    room_number: Annotated[str,
            Field(description="Room number shown on the sign, e.g. 'A-101'."),
            niceview.Field(table_label='Number')
        ] = '000'

    room_name: Annotated[str,
            Field(description="Human-readable room name, e.g. 'North Conference'."),
            niceview.Field(table_label='Name')
        ] = 'Room'

    building: Annotated[Optional[str],
            Field(description='Building the room is in.')
        ] = None

    floor: Annotated[Optional[str],
            Field(description="Floor/level, e.g. 'G', '1', '-1'.")
        ] = None

    room_type: Annotated[RoomType,
            Field(description='Kind of room.'),
            niceview.Field(widget_type='ui.select', options=ROOM_TYPE_LABELS, table_label='Type')
        ] = 'meeting'

    capacity: Annotated[Optional[int],
            Field(ge=0, description='Seating capacity (number of people).'),
            niceview.Field()
        ] = None
    
    notes: Annotated[Optional[str],
            Field(title="Notes (shown on displays)", description='Free-text notes to be shown on the sign.'),
            niceview.Field(widget_type='ui.textarea', table_hidden=True)
        ] = None

    description: Annotated[Optional[str],
            Field(description='Free-text description of the room.'),
            niceview.Field(widget_type='ui.textarea', table_hidden=True)
        ] = None

    # --- Booking source ---------------------------------------------------
    booking_system_id: Annotated[Optional[str],
            Field(title="Booking system",
                 description='Booking system (Settings > Booking systems) that feeds '
                             'this room. Empty = the room has no booking source yet.'),
            niceview.Field(widget_type='modelselect', item_type=BookingSystemModel, 
                           hint="Booking system providing the calendar")
        ] = None

    booking_ical_url: Annotated[str,
            Field(description='This room\'s own full feed URL, overriding the booking '
                              'system\'s URL entirely (not appended to it) -- for a system '
                              'where each room is its own resource on the same server (e.g. '
                              'Exchange: system = account/server, room = mailbox). Empty = '
                              'use the booking system\'s own URL as-is. Currently always an '
                              'iCal/ICS feed (the only BookingSystemType so far).'),
            niceview.Field(label='Booking System URL override',
                           hint='Overrides the booking system\'s URL entirely (not appended) '
                                '-- http(s):// or webcal://. Leave empty to use the booking '
                                'system\'s own URL.')
        ] = ""

    @field_validator("booking_ical_url")
    @classmethod
    def _check_ical_url(cls, v: Optional[str]) -> Optional[str]:
        # Lenient on purpose: empty is fine (inherit the system URL), and a
        # calendar feed is legitimately http(s):// or webcal://; anything else
        # is a typo worth catching before it silently never loads.
        if v and not v.startswith(("http://", "https://", "webcal://")):
            raise ValueError("iCal URL must start with http://, https:// or webcal://")
        return v

    @property
    def room_label(self) -> str:
        """Compact human label for this room: 'number (name)' when both are
        set, else whichever one isn't empty. Used wherever a room needs a
        single-line human-readable identifier (selects, list titles)."""
        if self.room_number and self.room_name:
            return f'{self.room_number} ({self.room_name})'
        return self.room_number or self.room_name

    class Meta:
        title = "Room"
        title_plural = "Rooms"
        layout = [
            ['## Room',
                ['room_number:w-1/4', 'room_name'],
                ['building', 'floor:w-1/4'],
                ['room_type', 'capacity:w-1/4'],
                'notes', 'description'],
            ['## Booking system', ['booking_system_id:shrink', 'booking_ical_url']],
        ]
