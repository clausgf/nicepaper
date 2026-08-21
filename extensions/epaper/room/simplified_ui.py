"""
Rooms section: a niceview DrillDownWrapper over the rooms directory
(rooms_adapter, a JsonDirectoryAdapter), so the list, Add and Delete are
niceview's; this module only
supplies the row and the detail body -- three tabs: Occupancy, Settings (the
RoomModel form, autosaving through the adapter), and Displays (the devices
bound to the room).

The form's field metadata (labels/widgets/hints) lives on RoomModel itself
(its fields' Annotated FieldInfo); only the visual layout is here.
"""
from nicegui import ui
from niceview import DrillDownWrapper, JsonDirectoryAdapter, ModelForm
import niceview

from extensions.epaper.bookingsystem.backend import list_booking_systems
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.room.backend import rooms_adapter
from extensions.epaper.room.models import RoomModel

from extensions.epaper.ui.simplified_ui.common import scaffold_note
from extensions.epaper.ui.simplified_ui.displays_grid import render_displays_grid
from extensions.epaper.ui.simplified_ui.layout import Shell


def render_rooms(shell: Shell) -> None:
    adapter = rooms_adapter(shell.paths)
    DrillDownWrapper(
        RoomModel, adapter,  # list title/description come from RoomModel.Meta
        item_title_field='room_name',
        item_subtitle_fields=['room_number', 'room_type', 'capacity'],
        render_detail=lambda a, key, set_key: _render_detail(shell, a, key),
    ).render()


def _render_detail(shell: Shell, adapter: JsonDirectoryAdapter[RoomModel], key: str) -> None:
    room = adapter.read(key)
    with ui.tabs().classes('w-full') as tabs:
        ui.tab('occupancy', label='Occupancy', icon='event_available')
        ui.tab('settings', label='Settings', icon='tune')
        ui.tab('displays', label='Displays', icon='tv')
    with ui.tab_panels(tabs, value='settings').classes('w-full'):
        with ui.tab_panel('occupancy'):
            _occupancy_panel(room)
        with ui.tab_panel('settings'):
            # field_infos come from RoomModel's Annotated FieldInfo; only the
            # layout and the runtime-dependent booking-system options are
            # supplied here (shared with the project-tab editor, room/ui.py).
            # Autosaves through the adapter.
            ModelForm.from_adapter(RoomModel, adapter, key, autosave=True,
                                   field_infos=booking_system_field_infos(shell.paths, room),
                                   ).render()
        with ui.tab_panel('displays'):
            _displays_panel(shell, key)


def _occupancy_panel(room: RoomModel) -> None:
    with ui.card().classes('w-full items-center gap-2 p-6'):
        ui.icon('meeting_room').classes('text-6xl text-primary')
        ui.label(room.room_name).classes('text-h4')
        ui.label(room.room_number).classes('text-subtitle1 text-grey')
    scaffold_note('Live occupancy will come from the room’s booking system.')


def _displays_panel(shell: Shell, room_id: str) -> None:
    """The displays in this room: the shared displays grid, filtered to the
    room (Add here assigns a device to the room; Remove unassigns it)."""
    render_displays_grid(shell.paths, shell.project_name, room_id=room_id)


def booking_system_field_infos(paths: EpaperPaths, room: RoomModel) -> dict:
    """Make booking_system_id a select of the configured systems ({id: name}).
    The options are runtime data, so they can't live on the model; passed here
    they merge over the model's FieldInfo. A stored-but-deleted system stays
    visible (like the screen editor keeps a dangling schedule selectable); with
    no systems yet the field falls back to a plain, hinted input."""
    options = {s.id: s.name for s in list_booking_systems(paths)}
    current = room.booking_system_id
    if current and current not in options:
        options = {**options, current: f'{current} (unknown)'}
    if options:
        return {'booking_system_id': niceview.Field(
            widget_type='ui.select', options=options, clearable=True)}
    return {'booking_system_id': niceview.Field(
        hint='No booking systems yet — add one in Settings')}
