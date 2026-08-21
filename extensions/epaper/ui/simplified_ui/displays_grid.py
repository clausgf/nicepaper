"""
The displays grid, reused by the room's Displays tab (filtered to the room)
and the top-level Displays section (all displays).

A niceview EditGridWrapper over RoomDisplaysAdapter: Remove and Refresh are
niceview's, inline edits to the Screen column persist through the adapter, and
Add (only in a room, where "add" means *assign* an existing device) opens a
device picker. Columns are sortable/searchable; the device link and the online
state render via cell HTML.
"""
from typing import Optional

import niceview
from nicegui import ui
from niceview import EditGridWrapper

from extensions.epaper.core.devicebinding import set_device_binding
from extensions.epaper.core.roomdisplay import RoomDisplaysAdapter, assignable_devices
from extensions.epaper.models.roomdisplay import RoomDisplayRow
from extensions.epaper.paths import EpaperPaths


def _online_dot(value) -> str:
    color = '#21ba45' if value else '#bbbbbb'
    return f'<span style="color:{color};font-size:14px">●</span>'


def _device_link(value) -> str:
    if not value:
        return ''
    return (f'<a href="{value}" target="_blank" title="Open device page" '
            f'style="text-decoration:none">'
            f'<i class="material-icons" style="font-size:18px;vertical-align:middle">open_in_new</i></a>')


def render_displays_grid(paths: EpaperPaths, project_name: str,
                         room_id: Optional[str] = None) -> None:
    project = project_name
    # '' is the "no screen" choice; the rest are the project's screens.
    screen_ids = [''] + sorted(p.stem for p in paths.screen_dir.glob('*.json'))
    adapter = RoomDisplaysAdapter(paths, project, room_id)

    wrapper = EditGridWrapper.from_adapter(
        RoomDisplayRow, adapter, inline_edit=True,
        add_button=None, edit_button=None, delete_button='Remove', refresh_button='Refresh',
        rowSelection='single',
        field_infos={'screen_id': niceview.Field(
            label='Screen', table_sortable=True, table_filterable=True,
            aggrid={'cellEditor': 'agSelectCellEditor', 'cellEditorParams': {'values': screen_ids}})},
        cell_renderers={'online': _online_dot, 'device_url': _device_link},
    )

    # Add = assign an existing device to this room (devices are provisioned in
    # nice4iot, not created here) -- only meaningful inside a room.
    if room_id is not None:
        ui.button('Add display', icon='add',
                  on_click=lambda: _assign_dialog(paths, project, room_id, wrapper)).props('unelevated')
    wrapper.render()


def _assign_dialog(paths: EpaperPaths, project_name: str, room_id: str,
                   wrapper: EditGridWrapper) -> None:
    names = assignable_devices(paths, project_name, room_id)
    with ui.dialog() as dialog, ui.card().classes('min-w-72 gap-2'):
        ui.label('Add display to this room').classes('text-subtitle1')
        if not names:
            ui.label('No assignable devices — provision one in nice4iot first.') \
                .classes('text-caption text-grey')
            with ui.row().classes('w-full justify-end'):
                ui.button('Close', on_click=dialog.close).props('flat')
        else:
            select = ui.select(names, label='Device').classes('w-full')

            def do_assign() -> None:
                if select.value:
                    set_device_binding(paths, select.value, room_id=room_id)
                    wrapper.grid.update_rows()
                dialog.close()

            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Add', on_click=do_assign).props('unelevated')
    dialog.open()
