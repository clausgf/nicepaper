"""
Content-only rendering functions shared across the screen and schedule
editors (screen_editor.py, schedule_editor.py) and the standalone/nice4iot
entry points: the global settings card, the shared directory_drilldown()
DrillDownWrapper factory, plus small helpers (_render_row, slide_class)
used by both editors. No page/route/chrome ownership, so these work
identically whether called from a standalone @ui.page route
(ui/standalone.py) or from inside nice4iot's project page / card system
(extensions/epaper/__init__.py's register(app)).
"""
from pathlib import Path
from typing import Callable, Union

from nicegui import ui
from babel.dates import format_datetime, get_timezone
from niceview.dataadapter import DirectoryAdapter, FileEntry
from niceview.form import ModelForm
from niceview.modellist import DrillDownWrapper

from extensions.epaper.config import app_config, resource_paths
from extensions.epaper.util import check_filename

# Slide-in-from-left/right for list<->detail switches: screen_editor.py's
# widget list<->detail, and niceview's own DrillDownWrapper (screens_wrapper/
# schedules_wrapper) uses an equivalent mechanism internally. These switches
# are all @ui.refreshable functions, which destroy and recreate their
# elements on every refresh rather than toggling a CSS class -- so a CSS
# *animation* (not *transition*) plays automatically on every recreation,
# with no JS/state wiring beyond picking left vs. right by navigation
# direction. shared=True lets this be registered once here at import time,
# before any page/client exists.
_SLIDE_CSS = '''
    @keyframes slide-in-right { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    @keyframes slide-in-left  { from { transform: translateX(-100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    .slide-in-right { animation: slide-in-right 0.25s ease-out; }
    .slide-in-left  { animation: slide-in-left  0.25s ease-out; }
'''
ui.add_css(_SLIDE_CSS, shared=True)


def slide_class(direction: str) -> str:
    """CSS class for a slide-in-from-left/right animation, keyed by
    navigation direction ('right' when drilling into a detail view,
    'left' when going back to a list)."""
    return 'slide-in-left' if direction == 'left' else 'slide-in-right'


def _render_row(form: ModelForm, *field_names: str, props: str = 'outlined dense') -> None:
    """Render several short fields side by side to save vertical space.
    Shared with screen_editor.py/schedule_editor.py (imported explicitly,
    not part of the public API of this module)."""
    with ui.row().classes('w-full gap-2'):
        for name in field_names:
            form.render_field(name, props=props).classes('flex-grow')


def _entry_caption(item: FileEntry) -> str:
    """'<formatted mtime>, <size>' caption for a DirectoryAdapter FileEntry row."""
    dt_format = app_config.date_format + ' ' + app_config.time_format
    mtime_str = format_datetime(item.mtime, format=dt_format, tzinfo=get_timezone(app_config.timezone), locale=app_config.locale)
    if item.size < 1024:
        size_str = f'{item.size} B'
    elif item.size < 1024**2:
        size_str = f'{item.size/1024:.1f} kiB'
    else:
        size_str = f'{item.size/1024**2:.1f} MiB'
    return f'{mtime_str}, {size_str}'


def directory_drilldown(dir_path: Path, default_content: Union[str, Callable[[], str]],
                         title: str, render_content: Callable[[str], None]) -> DrillDownWrapper:
    """
    Shared DrillDownWrapper wiring for a directory of JSON files, used
    identically by screen_editor.screens_wrapper() and
    schedule_editor.schedules_wrapper(): the "no custom dialogs" Add/Rename
    style from niceview's DirectoryAdapter example (examples/13_directory_
    drilldown.py) -- Add creates an "untitled-NN" file and opens it
    directly; Rename is an inline "Name" field in the detail view, wired to
    DirectoryAdapter.rename() on blur -- plus this project's bordered-list
    row styling (icon + filename + mtime/size caption).

    render_content(filename) renders the actual per-file editor body (e.g.
    screen_editor_content(paths, filename, image_base_url) with paths/
    image_base_url already bound by the caller); this function only owns
    the file-level list<->editor chrome around it.
    """
    directory = DirectoryAdapter(dir_path, default_content=default_content)

    def render_list_container(render_rows) -> None:
        with ui.list().style('width: 100%').props('bordered separator'):
            render_rows()

    def render_row(key: str, item: FileEntry, select) -> None:
        with ui.item(on_click=lambda: select()):
            with ui.item_section().props('avatar'):
                ui.icon('description')
            with ui.item_section():
                ui.item_label(item.name)
                ui.item_label(_entry_caption(item)).props('caption').classes('italic')

    def render_detail(adapter: DirectoryAdapter, key: str, set_key) -> None:
        def do_rename() -> None:
            new_name = name_input.value
            if not check_filename(f'{new_name}.json'):
                ui.notify(f'Invalid file name: "{new_name}".', type='negative')
                return
            try:
                set_key(adapter.rename(key, new_name))
            except ValueError as e:
                ui.notify(str(e), type='negative')

        name_input = ui.input('Name', value=key).classes('w-full').props('outlined dense')
        name_input.on('blur', do_rename)
        render_content(f'{key}.json')

    def handle_add() -> None:
        entry = directory.create()
        wrapper.open(entry.name)

    wrapper = DrillDownWrapper.from_adapter(
        FileEntry, directory,
        list_title=title, item_title_field='name', item_subtitle_fields=[],
        render_list_item=render_row,
        render_list_container=render_list_container,
        render_detail=render_detail,
        on_add=handle_add,
    )
    return wrapper


def dashboard_card(num_screens: int, num_schedules: int, open_url: str) -> None:
    """
    Compact always-visible summary card for nice4iot's project Dashboard
    tab (register_project_card('dashboard', ...) requires the card to
    build its own ui.card()). open_url is where the "open" button
    navigates -- resolved by the caller (project_url(project_name,
    tab='Screens')), since URL construction is nice4iot-specific and
    doesn't belong in this UI-only module.
    """
    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('E-Paper').classes('text-subtitle1 font-bold')
            ui.button(icon='open_in_new').props('flat dense round').on_click(lambda: ui.navigate.to(open_url))
        ui.label(f'{num_screens} screen(s), {num_schedules} schedule(s)').classes('text-caption text-grey-7')


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
