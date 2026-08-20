"""
Booking system model: a calendar source a room's door sign draws from.

A booking system is the *connection/type* (iCal today; Exchange and others
later). The room-specific resource -- e.g. the room's own iCal URL -- lives on
the RoomModel (booking_ical_url), so several rooms can share one system while
each shows its own calendar; for Exchange later the split is the same (system =
account/server, room = mailbox/resource).

Same conventions as RoomModel (models/room.py): a stable surrogate `id` (never
changed, the file name, referenced by RoomModel.booking_system_id) and niceview
form metadata on each field's Annotated FieldInfo. Stored one JSON file per
system in EpaperPaths.booking_dir. Type-specific settings will be added behind a
`type` switch when a second type arrives.
"""
import datetime
from typing import Annotated, Literal
from uuid import uuid4

import niceview
from pydantic import BaseModel, Field

BookingSystemType = Literal["iCal"]


class BookingSystemModel(BaseModel):
    id: Annotated[str,
            Field(default_factory=lambda: uuid4().hex,
                  description='Stable surrogate id: generated once, never changed, and also the '
                              "system's file name. It is what RoomModel.booking_system_id "
                              'references, so a system can be renamed freely.'),
            niceview.Field(editable=False, hidden=True)
        ]

    name: Annotated[str,
            Field(description="Human-readable name, e.g. 'iCal Uni'.")
        ] = 'Booking system'

    type: Annotated[BookingSystemType,
            Field(description='Which kind of calendar source this is.'),
            niceview.Field(widget_type='ui.select')
        ] = 'iCal'

    url: Annotated[str,
            Field(description='URL of the iCal/ICS feed.'),
            niceview.Field()
        ] = ""

    username: Annotated[str,
            Field(description='Username for HTTP Basic Auth, if any.'),
            niceview.Field()
        ] = ""

    password: Annotated[str,
            Field(description='Password for HTTP Basic Auth, if any.'),
            niceview.Field(password=True)
        ] = ""

    header: Annotated[str,
            Field(description='Optional HTTP header dictionary.'),
            niceview.Field(widget_type='ui.textarea', placeholder='{"Header-Name": "value"}')
        ] = '{\n  "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0"\n}'

    update_interval: Annotated[datetime.timedelta,
            Field(description='How often the system fetches the calendar feed.'),
        ] = datetime.timedelta(minutes=10)

    max_days_ahead: Annotated[datetime.timedelta,
            Field(default=30, description='Maximum number of days ahead to fetch events.'),
        ] = datetime.timedelta(days=30)

    description: Annotated[str,
            Field(description='Free-text notes about this booking system.'),
            niceview.Field(widget_type='ui.textarea')
        ] = ""

    class Meta:
        title = "Booking system"
        description = "A calendar source to determine a room's occupancy."
        layout = [
            ['name', 'type:shrink'], 
            'url', 
            ['username', 'password'], 
            'header', 
            ['update_interval', 'max_days_ahead'], 
            'description',
        ]
