"""
Content-only rendering functions: no page/route/chrome ownership, so
these work identically whether called from a standalone @ui.page route
(extensions/epaper/ui/standalone.py) or from inside nice4iot's project
page / card system (extensions/epaper/__init__.py's register(app)).

Navigation out of these functions happens via callbacks (on_select,
on_add, on_deleted, ...) rather than fixed URLs, since standalone mode
navigates to real routes while the nice4iot single-page mode switches
in-page view state instead.
"""
import datetime
import json
import os
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from nicegui import ui
from pydantic import BaseModel, ValidationError
from babel.dates import format_datetime, get_timezone
from niceview.dataadapter import JsonListAdapter
from niceview.form import ModelForm
from niceview.util import confirm_dialog

from extensions.epaper.config import app_config
from extensions.epaper.models.screenmodel import DateWidgetModel, RoomCalendarWidgetModel, ScreenModel, TextWidgetModel, WidgetModel
from extensions.epaper.models.updateschedulemodel import WeeklyScheduleModel
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.util import check_filename

item_types = {
    "screen": {'plural': 'screens'},
    "schedule": {'plural': 'schedules'},
}


def _get_sourcecode(classes_list) -> str:
    import inspect
    source = ''
    for cls in classes_list:
        source_lines, _ = inspect.getsourcelines(cls)
        source += ''.join(source_lines) + '\n'
    return source


def screen_image_view(url: str):
    img = ui.image(url)
    with ui.row().classes('w-full items-center justify-between'):
        ui.label(f'URL: ...{url[-40:]}').classes('italic')
        ui.button('Refresh', icon='refresh').on('click', lambda img=img: img.force_reload())


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
            ui.button(icon='add', on_click=lambda: add_file()).props('size=sm round outline')

    file_list_names = sorted(os.listdir(dir))
    with ui.list().style('width: 100%').props('bordered separator'):
        for filename in file_list_names:
            with ui.item(on_click=lambda f=filename: on_select(f)):
                with ui.item_section().props('avatar'):
                    ui.icon('description')
                with ui.item_section():
                    ui.item_label(filename)

                    fn = os.path.join(dir, filename)
                    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fn), tz=ZoneInfo("UTC"))
                    dt_format = app_config.date_format + ' ' + app_config.time_format
                    mtime_str = format_datetime(mtime, format=dt_format, tzinfo=get_timezone(app_config.timezone), locale=app_config.locale)

                    size = os.path.getsize(fn)
                    if size < 1024:
                        size_str = f'{size} B'
                    elif size < 1024**2:
                        size_str = f'{size/1024:.1f} KB'
                    else:
                        size_str = f'{size/1024**2:.1f} MB'

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
                content = ScreenModel(size=(800, 480)).model_dump_json(indent=2)
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


def screen_editor(paths: EpaperPaths, filename: str, image_base_url: str,
                   on_deleted: Callable[[], None], on_saved: Optional[Callable[[], None]] = None):
    """
    Screen editor content: raw JSON editor (validated against ScreenModel)
    plus live RGB/palette image previews. `image_base_url` is the display
    API prefix for this screen's images (differs between standalone and
    the nice4iot extension router).
    """
    dir = paths.screen_dir
    if not filename or not check_filename(filename) or not filename.endswith('.json'):
        ui.notify(f'Invalid file name: "{filename}".', type='negative')
        on_deleted()
        return
    if not os.path.exists(os.path.join(dir, filename)):
        ui.notify(f'File "{filename}" does not exist.', type='negative')
        on_deleted()
        return

    with open(os.path.join(dir, filename), 'r') as f:
        content = f.read()

    editor = ui.codemirror(language='json', theme='material')
    editor.set_value(content)
    with ui.row().classes('w-full place-content-end'):
        ui.button('Delete File', on_click=lambda: delete_file())
        ui.space()
        ui.button('Save', on_click=lambda: save_file())

    ui.separator()
    color_models = [cm.id for cm in app_config.epaper_color_models]
    screen_id = os.path.splitext(filename)[0]
    with ui.tabs().classes('w-full') as tabs:
        model_tab = ui.tab('Model source')
        rgb_tab = ui.tab('RGB')
        palette_tabs = [ui.tab(cm.id) for cm in app_config.epaper_color_models]
    with ui.tab_panels(tabs, value=model_tab).classes('w-full'):
        with ui.tab_panel(model_tab):
            classes = (ScreenModel, WidgetModel, TextWidgetModel, DateWidgetModel, RoomCalendarWidgetModel)
            ui.code(_get_sourcecode(classes), language='python').classes('w-full')
        with ui.tab_panel(rgb_tab):
            screen_image_view(f'{image_base_url}/{screen_id}/image.png')
        for i, tab in enumerate(palette_tabs):
            with ui.tab_panel(tab):
                screen_image_view(f'{image_base_url}/{screen_id}/image.png?color_model={color_models[i]}')

    with ui.dialog().style('width: 400px') as confirm_delete_dialog, ui.card():
        ui.label('Delete file').classes('text-h6 center')
        ui.label(f'Are you sure you want to delete "{filename}"?')
        with ui.row().classes('w-full place-content-end'):
            ui.space()
            ui.button('Cancel', on_click=lambda: confirm_delete_dialog.submit(False)).props('color=green')
            ui.button('Confirm', on_click=lambda: confirm_delete_dialog.submit(True)).props('color=red')

    async def delete_file():
        confirm = await confirm_delete_dialog
        if confirm:
            os.remove(os.path.join(dir, filename))
            ui.notify(f'File "{filename}" deleted.', type='positive')
            on_deleted()
        else:
            ui.notify(f'Canceled deleting "{filename}".', type='negative')

    def save_file():
        try:
            data = json.loads(editor.value)
            ScreenModel(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            ui.notify(f"Validation error: {e}", type='negative')
            return
        with open(os.path.join(dir, filename), 'w') as f:
            f.write(editor.value)
        ui.notify("File saved successfully.", type='positive')
        if on_saved:
            on_saved()


def schedule_editor(paths: EpaperPaths, filename: str, on_deleted: Callable[[], None]):
    """
    Edit a schedule as a card per weekly rule (WeeklyScheduleModel), backed
    by a niceview JsonListAdapter over the schedule file. Each card is an
    autosaving ModelForm bound to one list item; fields are placed by hand
    (niceview has no generic "card grid" widget, nor should it: which
    fields go where is inherently an application layout decision, not
    something a form library can generalize).
    """
    if not filename or not check_filename(filename) or not filename.endswith('.json'):
        ui.notify(f'Invalid file name: "{filename}".', type='negative')
        on_deleted()
        return

    schedule_path = paths.schedule_dir / filename
    if not schedule_path.exists():
        ui.notify(f'File "{filename}" does not exist.', type='negative')
        on_deleted()
        return

    adapter = JsonListAdapter(WeeklyScheduleModel, schedule_path)

    @ui.refreshable
    def rule_cards():
        rules = list(adapter.items())
        if not rules:
            ui.label('No weekly rules yet — add one below.').classes('italic')
        for key, _item in rules:
            form = ModelForm.from_adapter(WeeklyScheduleModel, adapter, key, autosave=True)
            with ui.card().classes('w-full q-mb-md'):
                with ui.row().classes('w-full items-center justify-between'):
                    ui.label('Weekly rule').classes('text-subtitle1')
                    ui.button(icon='delete').props('color=negative dense flat').on_click(
                        lambda _, k=key: delete_rule(k))
                # checkbox_group returns a composite CheckboxGroup, not a
                # ui.element itself -- style its .widget (the row/column) instead
                form.render_field('by_weekdays', widget_type='checkbox_group', props='inline').widget.classes('w-full')
                form.render_field('by_months').classes('w-full')
                # times: List[Annotated[str, pattern]] -> ui.input_chips, a real
                # ui.element (unlike checkbox_group/editgrid), so .classes() works
                form.render_field('times').classes('w-full')
                form.render_nonfield_errors()

    async def delete_rule(key: str):
        if not await confirm_dialog('Delete rule', 'Delete this weekly rule? This cannot be undone.',
                                     ok_label='Delete', ok_color='negative'):
            return
        adapter.delete(key)
        rule_cards.refresh()
        ui.notify('Rule deleted', type='positive')

    def add_rule():
        adapter.create(WeeklyScheduleModel(times=[]))
        rule_cards.refresh()

    with ui.row().classes('w-full place-content-end'):
        ui.button('Delete File', on_click=lambda: delete_schedule_file())
    rule_cards()
    ui.button('Add Rule', icon='add', on_click=lambda: add_rule()).props('color=primary')

    with ui.dialog().style('width: 400px') as confirm_delete_file_dialog, ui.card():
        ui.label('Delete file').classes('text-h6 center')
        ui.label(f'Are you sure you want to delete "{filename}"?')
        with ui.row().classes('w-full place-content-end'):
            ui.space()
            ui.button('Cancel', on_click=lambda: confirm_delete_file_dialog.submit(False)).props('color=green')
            ui.button('Confirm', on_click=lambda: confirm_delete_file_dialog.submit(True)).props('color=red')

    async def delete_schedule_file():
        confirm = await confirm_delete_file_dialog
        if confirm:
            os.remove(schedule_path)
            ui.notify(f'File "{filename}" deleted.', type='positive')
            on_deleted()
        else:
            ui.notify(f'Canceled deleting "{filename}".', type='negative')
