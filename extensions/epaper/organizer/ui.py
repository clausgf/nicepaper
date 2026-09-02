"""
Organizer names editor for the non-simplified UI: nice4iot's project
Settings sidebar group (its own 'settings' card, see __init__.py) and
standalone's Settings page. Content only, no ui.card()/ui.expansion() of its
own -- same contract as project_config_fields() -- so each host supplies its
own chrome. The simplified UI's own editor (organizer/simplified_ui.py's
render_organizer_names) has its own header/layout but shares
ORGANIZER_NAMES_DESCRIPTION below.
"""
from nicegui import ui

from extensions.epaper.organizer.backend import read_organizer_names, save_organizer_names
from extensions.epaper.paths import EpaperPaths

ORGANIZER_NAMES_DESCRIPTION = (
    "Names checked against an event's summary when its iCal feed has no "
    "ORGANIZER field: a summary starting with one of these names is credited "
    "to that organizer, and the name is stripped from the summary shown. "
    "One name per line."
)


def organizer_names_fields(paths: EpaperPaths) -> None:
    def handle_blur() -> None:
        names = [line.strip() for line in textarea.value.splitlines() if line.strip()]
        save_organizer_names(paths, names)
        ui.notify('Saved', type='positive')

    ui.label(ORGANIZER_NAMES_DESCRIPTION).classes('text-caption text-grey')
    textarea = ui.textarea(value='\n'.join(read_organizer_names(paths))) \
        .props('outlined').classes('w-full').on('blur', handle_blur)


def organizer_names_card(paths: EpaperPaths) -> None:
    """Card wrapper around organizer_names_fields(), for standalone.py's own
    Settings tab, which supplies no card chrome of its own (unlike nice4iot's
    'settings' project card, which renders the chrome for you -- see
    extensions/epaper/__init__.py's _organizer_names_card())."""
    with ui.card().classes('w-full'):
        ui.label('Organizer Names').classes('text-subtitle1')
        organizer_names_fields(paths)
