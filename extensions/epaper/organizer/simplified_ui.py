"""
Preferences > Organizer names: edit dialog for organizer_names_file, the flat
list core/datasources/ical.py falls back to when an event has no ORGANIZER
field. A read-only list plus an "Edit" button opening a dialog (title,
description, one textarea, one name per line) -- same list/Add shape as
bookingsystem/ui.py's header/category-color editors, minus the per-row add.
"""
from nicegui import ui

from extensions.epaper.organizer.backend import read_organizer_names, save_organizer_names
from extensions.epaper.ui.simplified_ui.common import view_header
from extensions.epaper.ui.simplified_ui.layout import Shell

_DESCRIPTION = (
    "Names checked against an event's summary when its iCal feed has no "
    "ORGANIZER field: a summary starting with one of these names is credited "
    "to that organizer, and the name is stripped from the summary shown. "
    "One name per line."
)


def render_organizer_names(shell: Shell) -> None:
    @ui.refreshable
    def body() -> None:
        names = read_organizer_names(shell.paths)
        with ui.list().props('bordered separator').classes('w-full'):
            if not names:
                with ui.item():
                    ui.item_label('No organizer names configured.').classes('italic text-grey')
            for name in names:
                with ui.item():
                    ui.item_label(name)

    with view_header('Organizer names', action='Edit',
                     on_action=lambda: _edit_dialog(shell, body.refresh)):
        pass
    body()


async def _edit_dialog(shell: Shell, on_saved) -> None:
    names = read_organizer_names(shell.paths)
    with ui.dialog() as dialog, ui.card().classes('min-w-96 gap-2'):
        ui.label('Organizer names').classes('text-subtitle1')
        ui.label(_DESCRIPTION).classes('text-caption text-grey')
        textarea = ui.textarea(value='\n'.join(names)).props('outlined').classes('w-full')
        with ui.row().classes('w-full justify-end'):
            ui.button('Cancel', on_click=lambda: dialog.submit(False)).props('flat')
            ui.button('Save', on_click=lambda: dialog.submit(True)).props('unelevated')
    if not await dialog:
        return
    save_organizer_names(shell.paths, [line.strip() for line in textarea.value.splitlines() if line.strip()])
    on_saved()
