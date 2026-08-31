"""
Preferences > Organizer names: direct editor for organizer_names_file, the
flat list core/datasources/ical.py falls back to when an event has no
ORGANIZER field. A single textarea (one name per line), saved on blur --
no separate edit dialog/button, since the textarea IS the editor.
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
    def handle_blur() -> None:
        names = [line.strip() for line in textarea.value.splitlines() if line.strip()]
        save_organizer_names(shell.paths, names)
        ui.notify('Saved', type='positive')

    with ui.column().classes('w-full h-full gap-4'):
        with view_header('Organizer names'):
            pass
        ui.label(_DESCRIPTION).classes('text-caption text-grey')
        textarea = ui.textarea(value='\n'.join(read_organizer_names(shell.paths))) \
            .props('outlined').classes('w-full flex-grow').on('blur', handle_blur)
