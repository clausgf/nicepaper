"""
Row view-model for a display (a nice4iot device showing a screen), one row
per device. This is a *view* model, not stored as-is: only `screen_id` is
editable and persisted (into the device binding, devicebinding/models.py);
everything else is read-only and joined together by display/backend.py from
the nice4iot device (name, online, last_seen_at) and the room the device is
bound to (building/floor/room number/room_label).

Fields are declared in display order;
their labels/sort/filter/editability ride each field's niceview FieldInfo
(used where a field is still rendered via ModelForm/ModelGrid; the simplified
UI's own display/simplified_ui.py mostly renders these by hand).
"""
import datetime
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

    room_label: Annotated[str,
            Field(description="Compact label of the display's room ('number (name)'), "
                              "empty if it isn't bound to one -- see RoomModel.room_label."),
            niceview.Field(label='Room', editable=False, table_sortable=True, table_filterable=True)
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
            niceview.Field(label='Room number', editable=False, table_sortable=True, table_filterable=True)
        ] = ''

    online: Annotated[bool,
            Field(description='Whether the device was seen recently.'),
            niceview.Field(label='Online', editable=False, table_sortable=True)
        ] = False

    last_seen_at: Annotated[Optional[datetime.datetime],
            Field(description='When the device was last seen by nice4iot (any authenticated '
                              'request or telemetry push), regardless of the online threshold.'),
            niceview.Field(label='Last seen', editable=False, table_sortable=True)
        ] = None

    firmware_version: Annotated[str,
            Field(description='Firmware version the device last reported. Empty if it never has.'),
            niceview.Field(label='Firmware', editable=False, table_sortable=True, table_filterable=True)
        ] = ''

    rssi: Annotated[Optional[int],
            Field(description='WiFi signal strength (dBm) from the last system-telemetry push. '
                              'Empty if the device never reported one.'),
            niceview.Field(label='RSSI', editable=False, table_sortable=True)
        ] = None

    battery_voltage: Annotated[Optional[float],
            Field(description='Battery voltage (V) from the last system-telemetry push. '
                              'Empty if the device never reported one.'),
            niceview.Field(label='Battery V', editable=False, table_sortable=True)
        ] = None

    alarm_count: Annotated[Optional[int],
            Field(description='Number of active alarms.'),
            niceview.Field(label='Alarms', editable=False, table_sortable=True)
        ] = None

    device_url: Annotated[str,
            Field(description='Link to the nice4iot device page (rendered as an icon).'),
            niceview.Field(label='', editable=False, table_sortable=False, table_filterable=False,
                           aggrid={'width': 64, 'sortable': False, 'filter': False, 'resizable': False})
        ] = ''
