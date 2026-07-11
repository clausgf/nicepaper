import asyncio
from contextlib import contextmanager
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from nicegui import context, ui
import os
import json
import inspect
from pydantic import BaseModel, ValidationError
from babel.dates import format_datetime, get_timezone
from niceview.dataadapter import JsonListAdapter
from niceview.form import ModelForm
from niceview.util import confirm_dialog


from app.auth import PasswordAuthProvider, get_auth_provider
from app.config import app_config
from app.models.screenmodel import DateWidgetModel, RoomCalendarWidgetModel, ScreenModel, TextWidgetModel, WidgetModel
from app.models.updateschedulemodel import WeeklyScheduleModel
from app.util import check_filename


router = APIRouter()

main_menu = [
    {'label': 'Home', 'icon': 'home', 'link': '/'},
    {'label': 'Screens', 'icon': 'image', 'link': '/screens'},
    {'label': 'Schedules', 'icon': 'calendar_today', 'link': '/schedules'},
]

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


def user_menu():
    provider = get_auth_provider()
    username = provider.get_user(context.client.request)

    def do_logout():
        provider.logout()
        ui.navigate.to(provider.logout_url() or '/')

    with ui.button(username or '', icon='person').props('flat color=white'):
        with ui.menu():
            if not username:
                ui.menu_item('Not signed in').props('disable')
            if provider.logout_url():
                with ui.menu_item(on_click=do_logout).classes('items-center gap-x-2'):
                    ui.icon('logout').props('size=large')
                    ui.label('Logout')


def screen_image(url: str):
    img = ui.image(url)
    with ui.row().classes('w-full items-center justify-between'):
        ui.label(f'URL: ...{url[4:]}').classes('italic')
        ui.button('Refresh', icon='refresh').on('click', lambda img=img: img.force_reload())


def login_redirect():
    """
    Server-side redirect to the login page for unauthenticated users, or
    None if the page may be shown. Call at the top of every protected
    page: 'if (redirect := login_redirect()): return redirect'. A
    server-side redirect ensures the page content is never rendered
    into the response for unauthenticated users.
    """
    provider = get_auth_provider()
    request = context.client.request
    if provider.login_required and provider.get_user(request) is None:
        root_path = request.scope.get('root_path', '') if request else ''
        return RedirectResponse(f"{root_path}/login")
    return None


@contextmanager
def frame(navigation_title: str, sidemenu_item_type: str = None, sidemenu_dir: str = None):
    """Page frame to share the same styling and navigation across all pages."""
    with ui.header(elevated=True).style('background-color: #3874c8').classes('items-center justify-between'):
        ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
        ui.label('Epaper Doorsign Manager').classes('font-bold')
        user_menu()
    with ui.left_drawer(fixed=False).style('background-color: #ebf1fa').props('bordered') as left_drawer:
        # main menu
        with ui.row().classes('w-full items-center'):
            for item in main_menu:
                ui.button(item['label'], icon=item['icon']).on('click', lambda l=item['link']: ui.navigate.to(l)).props('size=sm dense')
        ui.separator()
        show_files(sidemenu_item_type, sidemenu_dir)
    with ui.column().classes('w-full'):
        ui.label(navigation_title).classes('text-h5')
        ui.separator()
        yield


@ui.refreshable
def show_files(item_type: str, dir: str):
    if item_type is None or dir is None:
        ui.label('No items.').classes('italic')
        return

    # show list of files in the directory
    with ui.column().classes('w-full'):

        # header with button to add new file
        with ui.row().classes('w-full items-center justify-between'):
            plural = item_types[item_type]['plural']
            ui.label(f'{plural.capitalize()}').classes('text-h6')
            ui.button(icon='add', on_click=lambda: add_file()).props('size=sm round outline')

        # list of files
        file_list = sorted(os.listdir(dir))
        with ui.list().style('width: 100%').props('bordered separator'):
            #ui.item_label('Files').props('header').classes('text-bold')
            #ui.separator()
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
    with frame(f'Edit {item_type.lower()} {filename}', item_type, dir):
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


@ui.page('/login')
def page_login():
    provider = get_auth_provider()
    if not isinstance(provider, PasswordAuthProvider) or provider.get_user():
        root_path = context.client.request.scope.get('root_path', '') if context.client.request else ''
        return RedirectResponse(f"{root_path}/")

    with ui.card().classes('absolute-center items-stretch'):
        ui.label('Epaper Doorsign Manager').classes('text-h6')
        username = ui.input('Username').props('autofocus')
        password = ui.input('Password', password=True, password_toggle_button=True)

        async def try_login():
            # bcrypt verification is CPU bound, keep it off the event loop
            if await asyncio.to_thread(provider.verify, username.value, password.value):
                provider.login(username.value)
                ui.navigate.to('/')
            else:
                ui.notify('Wrong username or password', type='negative')

        username.on('keydown.enter', try_login)
        password.on('keydown.enter', try_login)
        ui.button('Log in', on_click=try_login).classes('w-full')


@ui.page('/screens')
def page_screens():
    if (redirect := login_redirect()):
        return redirect
    with frame('Select a screen to edit or add a new one', 'screen', app_config.screen_dir):
        show_files('screen', app_config.screen_dir)


@ui.page('/screens/{filename}')
async def page_screen_edit(filename: str):
    if (redirect := login_redirect()):
        return redirect
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
    if (redirect := login_redirect()):
        return redirect
    with frame('Select a schedule to edit or add a new one', 'schedule', app_config.schedule_dir):
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
    if (redirect := login_redirect()):
        return redirect

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
                form.render_field('by_weekdays').classes('w-full')
                form.render_field('by_months').classes('w-full')
                # 'times' resolves to an editgrid widget (ModelGrid/EditGridWrapper),
                # a plain wrapper object, not a ui.element -- no .classes() to chain
                form.render_field('times')
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

    with frame(f'Edit schedule {filename}', 'schedule', app_config.schedule_dir):
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


@ui.page('/')
def page_home():
    if (redirect := login_redirect()):
        return redirect
    with frame('Main Menu'):
        with ui.row():
            for item in main_menu:
                ui.button(item['label'], icon=item['icon']).on('click', lambda l=item['link']: ui.navigate.to(l)).props('size=xl stack').classes('w-48 h-32')
            ui.space()

