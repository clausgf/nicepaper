"""
Rooms section: a niceview DrillDownWrapper over the rooms directory
(rooms_adapter, a JsonDirectoryAdapter), so the list, Add and Delete are
niceview's; this module only supplies the row and the detail body -- three
tabs: Occupancy, Settings (the RoomModel form, autosaving through the
adapter), and Displays (a room summary plus its own drill-down list of the
devices bound to the room, see _displays_panel()).

The form's field metadata (labels/widgets/hints) lives on RoomModel itself
(its fields' Annotated FieldInfo); only the visual layout is here.
"""
from nicegui import ui
from niceview import DrillDownWrapper, JsonDirectoryAdapter, ModelForm
import niceview

from extensions.epaper.bookingsystem.backend import list_booking_systems
from extensions.epaper.display.backend import RoomDisplaysAdapter, assignable_devices, project_device_names
from extensions.epaper.display.models import RoomDisplayRow
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.room.backend import read_room, rooms_adapter
from extensions.epaper.room.models import ROOM_TYPE_LABELS, RoomModel

from extensions.epaper.ui.simplified_ui.common import scaffold_note
from extensions.epaper.ui.simplified_ui.layout import Shell


def render_rooms(shell: Shell) -> None:
    adapter = rooms_adapter(shell.paths)
    DrillDownWrapper(
        RoomModel, adapter,  # list title/description come from RoomModel.Meta
        item_title_field='room_label',
        item_subtitle_fields=['room_type', 'capacity'],
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


def _room_summary(room: RoomModel) -> None:
    """Compact room header for the Displays tab: label + type, and, smaller,
    building/floor -- so the room is identifiable without switching tabs."""
    with ui.column().classes('w-full gap-0 q-mb-md'):
        room_type_label = ROOM_TYPE_LABELS.get(room.room_type, room.room_type)
        ui.label(f'{room.room_label} · {room_type_label}').classes('text-subtitle1')
        location = ', '.join(v for v in (room.building, room.floor) if v)
        if location:
            ui.label(location).classes('text-caption text-grey')


def _displays_panel(shell: Shell, room_id: str) -> None:
    """The displays in this room: a room header plus a drill-down list of the
    devices bound to it (Title device name, Subtitle screen), each editable
    (its Screen) and deletable (unassigns it from the room). Add picks from
    the project's assignable devices -- there is nothing to type, so the
    wrapper's standard Add button drives a device picker instead of an
    empty new item."""
    room = read_room(shell.paths, room_id)
    _room_summary(room)

    adapter = RoomDisplaysAdapter(shell.paths, shell.project_name, room_id)

    async def handle_add() -> None:
        names = assignable_devices(shell.paths, shell.project_name, room_id)
        if not names:
            ui.notify('No assignable devices — provision one in nice4iot first.', type='warning')
            return
        with ui.dialog() as dialog, ui.card().classes('min-w-72 gap-2'):
            ui.label('Add display to this room').classes('text-subtitle1')
            select = ui.select(names, label='Device').classes('w-full')
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=lambda: dialog.submit(None)).props('flat')
                ui.button('Add', on_click=lambda: dialog.submit(select.value)).props('unelevated')
        device_name = await dialog
        if not device_name:
            return
        adapter.create(RoomDisplayRow(device_name=device_name))
        wrapper.open(device_name)

    wrapper = DrillDownWrapper(
        RoomDisplayRow, adapter,
        title='Displays',
        item_title_field='device_name',
        item_subtitle_fields=['screen_id'],
        on_add=handle_add,
        render_detail=lambda a, key, set_key: _display_detail(shell, a, key, set_key),
    )
    wrapper.render()


def _display_detail(shell: Shell, adapter: RoomDisplaysAdapter, key: str, set_key) -> None:
    """A bound device's own detail: Device (editable -- reassigns this row to
    a different nice4iot device, keeping the same room/screen; a plain select
    for now, over every project device -- see project_device_names()) and
    Screen (editable, likewise a plain select over the project's screen files
    for now -- TODO: once screens carry a richer label, e.g. panel_label,
    show that instead of the bare id). Delete (unassign from the room) is
    the wrapper's standard chrome.

    Device identifies the row (RoomDisplaysAdapter keys by device name), so
    changing it needs an explicit rename + set_key -- like the file editors'
    Name field (ui/drilldown.py) -- rather than the model form's normal
    autosave, which only ever updates in place under the key it was opened
    with. The body is a local @ui.refreshable so it can redraw itself
    against the new key once the rename actually lands.
    """
    paths, project_name = shell.paths, shell.project_name
    screen_ids = sorted(p.stem for p in paths.screen_dir.glob('*.json'))

    @ui.refreshable
    def body(current_key: str) -> None:
        row = adapter.read(current_key)
        device_names = project_device_names(project_name)
        if row.device_name not in device_names:
            device_names = [row.device_name, *device_names]  # keep a since-removed device selectable

        def on_device_change(e) -> None:
            try:
                new_key = adapter.rename(current_key, e.value)
            except (KeyError, ValueError) as exc:
                ui.notify(str(exc), type='negative')
                return
            set_key(new_key)
            body.refresh(new_key)

        ui.select(device_names, value=row.device_name, label='Device',
                 on_change=on_device_change).classes('w-full').props('outlined dense')

        ModelForm.from_adapter(RoomDisplayRow, adapter, current_key, autosave=True,
                               include=['screen_id'],
                               field_infos={'screen_id': niceview.Field(
                                   widget_type='ui.select', options=screen_ids, clearable=True)},
                               ).render()

    body(key)


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
