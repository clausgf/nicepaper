"""
Row view-model for the displays grid (EditGridWrapper), one row per e-paper
display (a nice4iot device). This is a *view* model, not stored as-is: only
`screen_id` is editable and persisted (into the device binding,
models/devicebinding.py); everything else is read-only and joined together
by core/roomdisplay.py from the nice4iot device (name, online) and the room
the device is bound to (building/floor/room number).

RSSI, battery voltage and alarm count have no per-device source in nice4iot
today (RSSI/battery are push-only telemetry, not stored readably), so they
stay empty until the extension interface exposes them -- see
docs/nice4iot-extension-wishlist.md. Columns are declared in display order;
their labels/sort/filter/editability ride each field's niceview FieldInfo.
"""
from typing import Annotated, Optional

import niceview
from pydantic import BaseModel, Field


class RoomDisplayRow(BaseModel):
    device_name: Annotated[str,
            Field(description='nice4iot device name; the display identifies itself by it.'),
            niceview.Field(label='Display', editable=False, table_sortable=True, table_filterable=True)
        ] = ''

    screen_id: Annotated[str,
            Field(description='Screen this display renders (the device binding target).'),
            niceview.Field(label='Screen', table_sortable=True, table_filterable=True)
        ] = ''

    building: Annotated[str,
            Field(description="Building of the display's room."),
            niceview.Field(label='Building', editable=False, table_sortable=True, table_filterable=True)
        ] = ''

    floor: Annotated[str,
            Field(description="Floor of the display's room."),
            niceview.Field(label='Floor', editable=False, table_sortable=True, table_filterable=True)
        ] = ''

    room_number: Annotated[str,
            Field(description="Number of the display's room."),
            niceview.Field(label='Room', editable=False, table_sortable=True, table_filterable=True)
        ] = ''

    online: Annotated[bool,
            Field(description='Whether the device was seen recently.'),
            niceview.Field(label='Online', editable=False, table_sortable=True)
        ] = False

    rssi: Annotated[Optional[int],
            Field(description='WiFi signal strength (dBm). Empty until nice4iot exposes it.'),
            niceview.Field(label='RSSI', editable=False, table_sortable=True)
        ] = None

    battery_voltage: Annotated[Optional[float],
            Field(description='Battery voltage (V). Empty until nice4iot exposes it.'),
            niceview.Field(label='Battery V', editable=False, table_sortable=True)
        ] = None

    alarm_count: Annotated[Optional[int],
            Field(description='Number of active alarms. Empty until nice4iot exposes it.'),
            niceview.Field(label='Alarms', editable=False, table_sortable=True)
        ] = None

    device_url: Annotated[str,
            Field(description='Link to the nice4iot device page (rendered as an icon).'),
            niceview.Field(label='', editable=False, table_sortable=False, table_filterable=False,
                           aggrid={'width': 64, 'sortable': False, 'filter': False, 'resizable': False})
        ] = ''
