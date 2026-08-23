"""
Booking system model: a calendar source a room's door sign draws from.

A booking system is the source of calendar data, e.g. an iCal server. The
booking system model contains all info needed to fetch and parse the calendar 
feed. The room-specific resource -- e.g. the room's own iCal URL -- lives on
the RoomModel (booking_ical_url), so several rooms can share one system while
each shows its own calendar; for Exchange later the split is the same (system =
account/server, room = mailbox/resource).
"""
import datetime
import json
from typing import Annotated, Dict, Literal
from uuid import uuid4

import niceview
from pydantic import BaseModel, Field, field_validator

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

    # a dict, not a JSON-text field: hand-rendered as a two-column list with a
    # delete icon per row (bookingsystem/simplified_ui.py's _header_editor),
    # not through ModelForm -- see BookingSystemModel.Meta.layout, which
    # omits it. hidden=True keeps it out of any *other* form that renders
    # this model without an explicit layout (e.g. RoomModel's modelselect).
    header: Annotated[Dict[str, str],
            Field(default_factory=lambda: {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0'},
                description='Extra HTTP headers sent with every request to the feed.'),
            niceview.Field(hidden=True)
        ]

    @field_validator('header', mode='before')
    @classmethod
    def _migrate_legacy_header(cls, v):
        # pre-0.19 stored header as JSON text (a plain textarea); coerce it to
        # the dict this field is now typed as, so files written before this
        # change still load instead of failing validation.
        if isinstance(v, str):
            return json.loads(v) if v.strip() else {}
        return v

    # a dict, not a JSON-text field -- hand-rendered as a color-swatch list with
    # a delete icon per row (bookingsystem/simplified_ui.py's
    # _category_color_editor), same shape as header above. hidden=True for the
    # same reason: keep it out of any *other* form that renders this model
    # without an explicit layout (e.g. RoomModel's modelselect).
    category_colors: Annotated[Dict[str, str],
            Field(default_factory=dict,
                 description="Maps an iCal event's CATEGORIES entry to a color "
                             "(hex, e.g. '#ff0000') for RoomCalendar cards. A "
                             "color not in the panel's palette is approximated "
                             "to the nearest palette color at render time."),
            niceview.Field(hidden=True)
        ]

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

    def __str__(self) -> str:
        # The label niceview shows for a booking system in a modelselect (e.g.
        # the room grid/edit dialog's "Booking system" column) -- its name, not
        # the default pydantic field dump.
        return f"{self.name} ({self.id})"

    class Meta:
        title = "Booking system"
        title_plural = "Booking systems"
        description = "A calendar source to determine a room's occupancy."
        layout = [
            ['name', 'type:shrink'],
            'url',
            ['username', 'password'],
            ['update_interval', 'max_days_ahead'],
            'description',
        ]
