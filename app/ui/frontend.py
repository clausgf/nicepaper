from contextlib import contextmanager
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import APIRouter
from nicegui import ui
import os
import json
import inspect
from pydantic import BaseModel, ValidationError
from babel.dates import format_datetime, get_timezone
from niceview.dataadapter import JsonListAdapter
from niceview.form import ModelForm
from niceview.util import confirm_dialog


from app.config import app_config
from app.models.screenmodel import DateWidgetModel, RoomCalendarWidgetModel, ScreenModel, TextWidgetModel, WidgetModel
from app.models.updateschedulemodel import WeeklyScheduleModel
from app.util import check_filename


router = APIRouter()

# top-level navigation: two tabs, each its own route (not client-side
# panel switching), so /screens and /schedules stay deep-linkable
TAB_ROUTES = {'Screens': '/screens', 'Schedules': '/schedules'}

item_types = {
    "screen": {'plural': 'screens', 'actions': [
        {'id':'edit', 'label': 'Edit screen', 'icon': 'edit', 'link': '/screens/{}'},
        {'id':'list', 'label': 'List all screens', 'icon': 'list', 'link': '/screens'},
    ]},
    "schedule": {'plural': 'schedules', 'actions': [
        {'id':'edit', 'label': 'Edit schedule', 'icon': 'edit', 'link': '/schedules/{}'},
        {'id':'list', 'label': 'List all schedules', 'icon': 'list', 'link': '/schedules'},
    ]},
}

def get_action_link(item_type: str, action_id: str, filename: str = '') -> str:
    action = next((a for a in item_types[item_type]['actions'] if a['id'] == action_id), None)
    if action is None:
        return '/'
    return action['link'].format(filename)


def get_sourcecode(classes_list):
    source = ''
    for cls in classes_list:
        source_lines, _ = inspect.getsourcelines(cls)
        source += ''.join(source_lines) + '\n'
    return source


def screen_image(url: str):
    img = ui.image(url)
    with ui.row().classes('w-full items-center justify-between'):
        ui.label(f'URL: ...{url[4:]}').classes('italic')
        ui.button('Refresh', icon='refresh').on('click', lambda img=img: img.force_reload())


@contextmanager
def frame(navigation_title: str, active_tab: str = None):
    """Page frame to share the same styling and navigation across all pages."""
    def on_tab_change(e):
        if e.value != active_tab:
            ui.navigate.to(TAB_ROUTES[e.value])

    with ui.header(elevated=True).style('background-color: #3874c8').classes('items-center justify-between'):
        ui.label('Epaper Doorsign Manager').classes('font-bold')
        with ui.tabs(value=active_tab, on_change=on_tab_change).props('dense indicator-color=white').classes('text-white'):
            ui.tab('Screens')
            ui.tab('Schedules')
    with ui.column().classes('w-full'):
        ui.label(navigation_title).classes('text-h5')
        ui.separator()
        yield


@ui.refreshable
def show_files(item_type: str, dir: str):
    # header with button to add new file
    with ui.row().classes('w-full items-center justify-between'):
        plural = item_types[item_type]['plural']
        ui.label(f'{plural.capitalize()}').classes('text-h6')
        ui.button(icon='add', on_click=lambda: add_file()).props('size=sm round outline')

    # list of files
    file_list = sorted(os.listdir(dir))
    with ui.list().style('width: 100%').props('bordered separator'):
        for filename in file_list:
            with ui.item(on_click=lambda l=get_action_link(item_type, 'edit', filename): ui.navigate.to(l)):
                with ui.item_section().props('avatar'):
                    ui.icon('description')
                with ui.item_section():
                    ui.item_label(filename)

                    # determine last modified date
                    fn = os.path.join(dir, filename)
                    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fn), tz=ZoneInfo("UTC"))
                    dt_format = app_config.date_format + ' ' + app_config.time_format
                    mtime_str = format_datetime(mtime, format=dt_format, tzinfo=get_timezone(app_config.timezone), locale=app_config.locale)

                    # determine file size
                    size = os.path.getsize(os.path.join(dir, filename))
                    if size < 1024:
                        size_str = f'{size} B'
                    elif size < 1024**2:
                        size_str = f'{size/1024:.1f} KB'
                    else:
                        size_str = f'{size/1024**2:.1f} MB'

                    ui.item_label(mtime_str + ', ' + size_str).props('caption').classes('italic')

    # dialog for adding file and entering file name
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

        # determine default content
        if item_type == 'screen':
            content = ScreenModel(size=(800, 480)).model_dump_json(indent=2)
        elif item_type == 'schedule':
            content = '[]'  # a schedule file is a plain List[WeeklyScheduleModel]
        else:
            ui.notify(f'Unknown item type "{item_type}".', type='negative')
            return

        # write default content to file
        with open(os.path.join(dir, filename), 'w') as f:
            f.write(content)

        show_files.refresh(item_type, dir)
        ui.notify(f'File "{filename}" added.', type='positive')
        ui.navigate.to(get_action_link(item_type, 'edit', filename))


@contextmanager
def frame_with_json_editor(item_type: str, dir: str, filename: str, modelClass: type[BaseModel]):
    active_tab = 'Screens' if item_type == 'screen' else 'Schedules'

    # check filename to consist of alphanumeric characters and underscores
    if not filename or not check_filename(filename) or not filename.endswith('.json'):
        ui.notify(f'Invalid file name: "{filename}".', type='negative')
        ui.navigate.to(get_action_link(item_type, 'list'))
        yield # we always need to yield in a context manager
        return

    # check if file exists
    if not os.path.exists(os.path.join(dir, filename)):
        ui.notify(f'File "{filename}" does not exist.', type='negative')
        ui.navigate.to(get_action_link(item_type, 'list'))
        yield # we always need to yield in a context manager
        return

    # read file content
    with open(os.path.join(dir, filename), 'r') as f:
        content = f.read()

    # create editor for file content
    with frame(f'Edit {item_type.lower()} {filename}', active_tab):
        editor = ui.codemirror(language='json', theme='material')
        editor.set_value(content)
        with ui.row().classes('w-full place-content-end'):
            ui.button('Delete File', on_click=lambda: delete_file())
            ui.space()
            ui.button('Save', on_click=lambda: save_file())
        yield

    # dialog for confirming file deletion
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
            show_files.refresh(item_type, dir)
            ui.navigate.to(get_action_link(item_type, 'list'))
        else:
            ui.notify(f'Canceled deleting "{filename}".', type='negative')

    def save_file():
        if filename:
            content = editor.value
            is_valid, message = validate_json(content)
            if is_valid:
                with open(os.path.join(dir, filename), 'w') as f:
                    f.write(content)
                ui.notify("File saved successfully.", type='positive')
                show_files.refresh(item_type, dir)
            else:
                ui.notify(f"Validation error: {message}", type='negative')

    def validate_json(content):
        try:
            data = json.loads(content)
            modelClass(**data)
            return True, "Valid JSON"
        except (json.JSONDecodeError, ValidationError) as e:
            return False, str(e)


@ui.page('/')
def page_home():
    ui.navigate.to('/screens')


@ui.page('/screens')
def page_screens():
    with frame('Select a screen to edit or add a new one', 'Screens'):
        show_files('screen', app_config.screen_dir)


@ui.page('/screens/{filename}')
async def page_screen_edit(filename: str):
    with frame_with_json_editor('screen', app_config.screen_dir, filename, ScreenModel):
        ui.separator()
        color_models = [cm.id for cm in app_config.epaper_color_models]
        with ui.tabs().classes('w-full') as tabs:
            model_tab = ui.tab('Model source')
            rgb_tab = ui.tab('RGB')
            palette_tabs = [ui.tab(cm.id) for cm in app_config.epaper_color_models]
        with ui.tab_panels(tabs, value=model_tab).classes('w-full'):
            with ui.tab_panel(model_tab):
                classes = (ScreenModel, WidgetModel, TextWidgetModel, DateWidgetModel, RoomCalendarWidgetModel)
                ui.code(get_sourcecode(classes), language='python').classes('w-full')
            with ui.tab_panel(rgb_tab):
                screen_image(f'/../api/screen/{os.path.splitext(filename)[0]}/image.png')
            for i, tab in enumerate(palette_tabs):
                with ui.tab_panel(tab):
                    screen_image(f'/../api/screen/{os.path.splitext(filename)[0]}/image.png?color_model={color_models[i]}')


@ui.page('/schedules')
def page_schedules():
    with frame('Select a schedule to edit or add a new one', 'Schedules'):
        show_files('schedule', app_config.schedule_dir)


@ui.page('/schedules/{filename}')
async def page_schedule_edit(filename: str):
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
        ui.navigate.to(get_action_link('schedule', 'list'))
        return

    schedule_path = Path(app_config.schedule_dir) / filename
    if not schedule_path.exists():
        ui.notify(f'File "{filename}" does not exist.', type='negative')
        ui.navigate.to(get_action_link('schedule', 'list'))
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

    with frame(f'Edit schedule {filename}', 'Schedules'):
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
            show_files.refresh('schedule', app_config.schedule_dir)
            ui.navigate.to(get_action_link('schedule', 'list'))
        else:
            ui.notify(f'Canceled deleting "{filename}".', type='negative')
