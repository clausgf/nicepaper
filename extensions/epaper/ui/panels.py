"""
Content-only rendering functions shared across the screen and schedule
editors (screen_editor.py, schedule_editor.py) and the standalone/nice4iot
entry points: file listing, renaming, and the global settings card. No
page/route/chrome ownership, so these work identically whether called from
a standalone @ui.page route (extensions/epaper/ui/standalone.py) or from
inside nice4iot's project page / card system (extensions/epaper/__init__.py's
register(app)).

Navigation out of these functions happens via callbacks (on_select,
on_add, on_deleted, ...) rather than fixed URLs, since standalone mode
navigates to real routes while the nice4iot single-page mode switches
in-page view state instead.
"""
import datetime
import os
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from nicegui import ui
from babel.dates import format_datetime, get_timezone
from niceview.form import ModelForm

from extensions.epaper.config import app_config, resource_paths
from extensions.epaper.models.screenmodel import ScreenModel
from extensions.epaper.util import check_filename

item_types = {
    "screen": {'plural': 'screens'},
    "schedule": {'plural': 'schedules'},
}


def _render_row(form: ModelForm, *field_names: str, props: str = 'outlined dense') -> None:
    """Render several short fields side by side to save vertical space.
    Shared with screen_editor.py/schedule_editor.py (imported explicitly,
    not part of the public API of this module)."""
    with ui.row().classes('w-full gap-2'):
        for name in field_names:
            form.render_field(name, props=props).classes('flex-grow')


def _rename_file(dir: Path, old_path: Path, new_name: str) -> tuple[bool, str]:
    """Validate and perform renaming old_path to new_name within dir.
    Returns (success, a user-facing notification message). Shared between
    screen_editor's and schedule_editor's rename dialogs (each has its own
    local `rename_file()` closure as the button handler -- named
    differently from this module-level helper on purpose, since a nested
    `async def rename_file()` referencing a same-named module-level
    function would instead recurse into itself)."""
    if not new_name.endswith('.json'):
        new_name += '.json'
    if not check_filename(new_name):
        return False, f'Invalid file name: "{new_name}".'
    new_path = dir / new_name
    if new_path.exists():
        return False, f'File "{new_name}" already exists.'
    old_path.rename(new_path)
    return True, f'Renamed to "{new_name}".'


def global_config_card(persist: Callable[[], None]) -> None:
    """
    One editable card (as nice4iot's register_global_card() and the
    standalone "Global" tab both expect a single project-independent card)
    for the shared GlobalConfig singleton, app_config. ModelForm.from_item
    binds directly to that object -- not a fresh copy from an adapter --
    so autosave edits mutate app_config's own attributes in place: every
    module that already did `from extensions.epaper.config import
    app_config` sees the changes without needing to change anything.
    `persist()` is the caller's job (write to the right JSON path for
    standalone vs. the nice4iot extension); this function doesn't know or
    care which.
    """
    font_names = sorted(p.name for p in resource_paths.font_path.glob('*') if p.is_file())
    with ui.card().classes('w-full'):
        ui.label('E-Paper Global Settings').classes('text-subtitle1')
        form = ModelForm.from_item(app_config, exclude=['epaper_color_models'], on_change=lambda e: persist())

        with ui.column().classes('w-full gap-2'):
            ui.label('General').classes('text-subtitle2')
            _render_row(form, 'locale', 'timezone')
            _render_row(form, 'date_format', 'time_format')

            ui.label('Font & Colors').classes('text-subtitle2')
            with ui.row().classes('w-full gap-2'):
                form.render_field('font_name', widget_type='ui.select', select_options=font_names,
                                   props='outlined dense').classes('flex-grow')
                form.render_field('font_size', props='outlined dense').classes('flex-grow')
            with ui.row().classes('w-full gap-2'):
                form.render_field('color_background', widget_type='ui.color_input', props='outlined dense').classes('flex-grow')
                form.render_field('color_primary', widget_type='ui.color_input', props='outlined dense').classes('flex-grow')
                form.render_field('color_accent', widget_type='ui.color_input', props='outlined dense').classes('flex-grow')

            ui.label('iCal (Room Calendar)').classes('text-subtitle2')
            _render_row(form, 'ical_update_interval_s', 'ical_max_days')
            form.render_field('ical_error', props='outlined dense').classes('w-full')
            _render_row(form, 'no_appointments', 'next_appointment')
            _render_row(form, 'current_appointment', 'further_appointments')
            _render_row(form, 'roomcalendar_date_format_long', 'roomcalendar_date_format_short', 'roomcalendar_time_format')

            ui.label('Weather').classes('text-subtitle2')
            form.render_field('weather_update_interval_s', props='outlined dense').classes('w-full')
            form.render_field('weather_error', props='outlined dense').classes('w-full')

            form.render_nonfield_errors()


@ui.refreshable
def file_list(dir: Path, item_type: str, on_select: Callable[[str], None], on_add: Optional[Callable[[str], None]] = None):
    """
    List the JSON files in `dir` with an "add" button. on_select(filename)
    is called when a file is clicked; on_add(filename) after a new file is
    created (typically to navigate/switch to editing it). Pass on_add=None
    to hide the add button (e.g. a read-only context).
    """
    with ui.row().classes('w-full items-center justify-between'):
        plural = item_types[item_type]['plural']
        ui.label(f'{plural.capitalize()}').classes('text-h6')
        if on_add is not None:
            ui.button(icon='add', on_click=lambda: add_file()).props('round size=sm')

    file_list_names = sorted(os.listdir(dir))
    with ui.list().style('width: 100%').props('bordered separator'):
        for filename in file_list_names:
            with ui.item(on_click=lambda f=filename: on_select(f)):
                with ui.item_section().props('avatar'):
                    ui.icon('description')
                with ui.item_section():
                    ui.item_label(filename.strip('.json'))

                    fn = os.path.join(dir, filename)
                    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fn), tz=ZoneInfo("UTC"))
                    dt_format = app_config.date_format + ' ' + app_config.time_format
                    mtime_str = format_datetime(mtime, format=dt_format, tzinfo=get_timezone(app_config.timezone), locale=app_config.locale)

                    size = os.path.getsize(fn)
                    if size < 1024:
                        size_str = f'{size} B'
                    elif size < 1024**2:
                        size_str = f'{size/1024:.1f} kiB'
                    else:
                        size_str = f'{size/1024**2:.1f} MiB'

                    ui.item_label(mtime_str + ', ' + size_str).props('caption').classes('italic')

    if on_add is not None:
        with ui.dialog().style('width: 1800px') as add_file_dialog, ui.card():
            ui.label(f'Add new {item_type}').classes('text-h6 center')
            new_filename = ui.input("Enter the name of the new file").props('placeholder=filename.json').classes('w-full')
            with ui.row().classes('w-full place-content-end'):
                ui.space()
                ui.button('Cancel', on_click=lambda: add_file_dialog.submit(None))
                ui.button('Add', on_click=lambda: add_file_dialog.submit(new_filename.value))

        async def add_file():
            filename = await add_file_dialog
            if filename and not filename.endswith('.json'):
                filename += '.json'
            if not filename or not check_filename(filename):
                ui.notify('Canceled adding new file.', type='negative')
                return
            if os.path.exists(os.path.join(dir, filename)):
                ui.notify(f'File "{filename}" already exists.', type='negative')
                return

            if item_type == 'screen':
                content = ScreenModel(width=800, height=480).model_dump_json(indent=2)
            elif item_type == 'schedule':
                content = '[]'  # a schedule file is a plain List[WeeklyScheduleModel]
            else:
                ui.notify(f'Unknown item type "{item_type}".', type='negative')
                return

            with open(os.path.join(dir, filename), 'w') as f:
                f.write(content)

            file_list.refresh(dir, item_type, on_select, on_add)
            ui.notify(f'File "{filename}" added.', type='positive')
            on_add(filename)
