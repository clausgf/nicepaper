"""
Displays: the simplified UI's flat, project-wide list of e-paper displays.

A display is a nice4iot device (see extensions/epaper/__init__.py,
register_device_card). `render_displays()` is the top-level section (all
displays, no room filter, no Add) built on `render_displays_grid()` -- a
niceview EditGridWrapper over RoomDisplaysAdapter: Remove and Refresh are
niceview's, inline edits to the Screen column persist through the adapter.
Columns are sortable/searchable; the device link and the online state render
via cell HTML. room/simplified_ui.py's Displays tab has its own drill-down
list instead (room-scoped, one device at a time), not this grid.
"""
import niceview
from niceview import EditGridWrapper

from extensions.epaper.display.backend import RoomDisplaysAdapter
from extensions.epaper.display.models import RoomDisplayRow
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.simplified_ui.layout import Shell


def render_displays(shell: Shell) -> None:
    """The Displays section: every device in the project, with its room, online
    state and screen. Assigning a display to a room happens in the room's
    Displays tab (or the device's E-Paper card), so there is no Add here."""
    render_displays_grid(shell.paths, shell.project_name)


def _online_dot(value) -> str:
    color = '#21ba45' if value else '#bbbbbb'
    return f'<span style="color:{color};font-size:14px">●</span>'


def _device_link(value) -> str:
    if not value:
        return ''
    return (f'<a href="{value}" target="_blank" title="Open device page" '
            f'style="text-decoration:none">'
            f'<i class="material-icons" style="font-size:18px;vertical-align:middle">open_in_new</i></a>')


def render_displays_grid(paths: EpaperPaths, project_name: str) -> None:
    """The flat, project-wide grid: every display, unfiltered, no Add (a
    display is a nice4iot device -- assigning one to a room happens in the
    room's own Displays tab, room/simplified_ui.py)."""
    # '' is the "no screen" choice; the rest are the project's screens.
    screen_ids = [''] + sorted(p.stem for p in paths.screen_dir.glob('*.json'))
    adapter = RoomDisplaysAdapter(paths, project_name)

    wrapper = EditGridWrapper.from_adapter(
        RoomDisplayRow, adapter, inline_edit=True,
        add_button=None, edit_button=None, delete_button='', refresh_button='',
        rowSelection='single',
        field_infos={'screen_id': niceview.Field(
            label='Screen', table_sortable=True, table_filterable=True,
            aggrid={'cellEditor': 'agSelectCellEditor', 'cellEditorParams': {'values': screen_ids}})},
        cell_renderers={'online': _online_dot, 'device_url': _device_link},
    )
    wrapper.render()
