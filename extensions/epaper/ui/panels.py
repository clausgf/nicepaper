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
import os
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from nicegui import ui
from nicegui.events import SortableEventArguments
from pydantic import BaseModel
from babel.dates import format_datetime, get_timezone
from niceview.dataadapter import JsonAdapter, JsonListAdapter, ListAdapter
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

WIDGET_MODELS: dict[str, type[WidgetModel]] = {
    'Text': TextWidgetModel,
    'Date': DateWidgetModel,
    'RoomCalendar': RoomCalendarWidgetModel,
}
WIDGET_ICONS: dict[str, str] = {
    'Text': 'text_fields',
    'Date': 'event',
    'RoomCalendar': 'calendar_month',
}


def _widget_label(widget: WidgetModel) -> str:
    """Short label identifying a widget instance in the widget list."""
    if isinstance(widget, TextWidgetModel):
        return widget.text or '(empty text)'
    if isinstance(widget, DateWidgetModel):
        return widget.date_format or 'Date'
    if isinstance(widget, RoomCalendarWidgetModel):
        return widget.room_name or widget.room_number or '(room calendar)'
    return widget.widget_type


def _default_widget(widget_type: str) -> WidgetModel:
    """A new widget of the given type with placeholder values for its
    required fields -- filled in by the user in the detail form right
    after creation."""
    if widget_type == 'Text':
        return TextWidgetModel(position=(0, 0), text='')
    if widget_type == 'Date':
        return DateWidgetModel(position=(0, 0))
    if widget_type == 'RoomCalendar':
        return RoomCalendarWidgetModel(position=(0, 0), room_number='', room_name='', ical_url='')
    raise ValueError(f'Unknown widget type: {widget_type}')


def _render_int_pair(item: BaseModel, field_name: str, title: str, labels: tuple[str, str],
                      persist: Callable[[], None], allow_none: bool = False) -> None:
    """
    Two ui.number inputs bound to a Tuple[int, int] field (optionally
    Optional[Tuple[int, int]] when allow_none), persisting via persist()
    on change. niceview has no built-in tuple widget -- an unrecognised
    field type falls back to a plain ui.input bound to a raw string,
    which would silently store the wrong type here -- so position/size
    fields are hand-rolled instead of going through ModelForm.render().
    """
    current = getattr(item, field_name)
    with ui.row().classes('w-full items-center gap-2'):
        ui.label(title).classes('text-caption w-28')
        enabled = ui.switch(value=current is not None) if allow_none else None
        a = ui.number(label=labels[0], value=(current[0] if current else 0), precision=0).classes('w-24')
        b = ui.number(label=labels[1], value=(current[1] if current else 0), precision=0).classes('w-24')
        if enabled is not None:
            a.bind_enabled_from(enabled, 'value')
            b.bind_enabled_from(enabled, 'value')

        def _apply() -> None:
            if enabled is not None and not enabled.value:
                setattr(item, field_name, None)
            else:
                setattr(item, field_name, (int(a.value), int(b.value)))
            persist()

        a.on('blur', lambda: _apply())
        b.on('blur', lambda: _apply())
        if enabled is not None:
            enabled.on_value_change(lambda: _apply())


def _render_font_field(item: WidgetModel, persist: Callable[[], None]) -> None:
    """Optional[Tuple[str, int]] font field: font file name (select, from
    app_config.font_path) + point size. Same rationale as _render_int_pair
    for not using ModelForm's generic field rendering."""
    font_names = sorted(p.name for p in app_config.font_path.glob('*') if p.is_file())
    current = item.font
    with ui.row().classes('w-full items-center gap-2'):
        ui.label('Font').classes('text-caption w-28')
        enabled = ui.switch(value=current is not None)
        name_select = ui.select(font_names, label='Font file',
                                 value=(current[0] if current else (font_names[0] if font_names else None))).classes('w-60')
        size_number = ui.number(label='Size', value=(current[1] if current else 16), precision=0, min=1).classes('w-20')
        name_select.bind_enabled_from(enabled, 'value')
        size_number.bind_enabled_from(enabled, 'value')

        def _apply() -> None:
            if enabled.value:
                item.font = (name_select.value, int(size_number.value))
            else:
                item.font = None
            persist()

        enabled.on_value_change(lambda: _apply())
        name_select.on_value_change(lambda: _apply())
        size_number.on('blur', lambda: _apply())


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


def screen_editor(paths: EpaperPaths, filename: str, image_base_url: str, on_deleted: Callable[[], None]):
    """
    Screen editor content: screen-level settings, a drag-reorderable list
    of widgets that drills down into a per-type detail form, plus live
    RGB/palette image previews (always visible on top, since they reflect
    whichever widget/setting was just edited). `image_base_url` is the
    display API prefix for this screen's images (differs between
    standalone and the nice4iot extension router).

    All edits autosave through `screen_adapter` (a single JsonAdapter for
    the whole screen file, shared by every widget below) -- widgets are a
    nested list field, not their own JSON array, so niceview's
    JsonListAdapter (which assumes the file *is* the array) doesn't apply;
    ListAdapter wraps the in-memory `screen.widgets` list instead, with
    persistence wired up via on_change().
    """
    if not filename or not check_filename(filename) or not filename.endswith('.json'):
        ui.notify(f'Invalid file name: "{filename}".', type='negative')
        on_deleted()
        return
    screen_path = paths.screen_dir / filename
    if not screen_path.exists():
        ui.notify(f'File "{filename}" does not exist.', type='negative')
        on_deleted()
        return

    screen_adapter = JsonAdapter(ScreenModel, screen_path)
    screen = screen_adapter.read()

    def persist_screen() -> None:
        screen_adapter.save(screen)

    widgets_adapter = ListAdapter(WidgetModel, screen.widgets)
    widgets_adapter.on_change(persist_screen)

    state = {'view': 'list', 'key': None}

    with ui.row().classes('w-full place-content-end'):
        ui.button('Delete File', on_click=lambda: delete_file())

    ui.separator()
    color_models = [cm.id for cm in app_config.epaper_color_models]
    screen_id = os.path.splitext(filename)[0]
    with ui.tabs().classes('w-full') as tabs:
        rgb_tab = ui.tab('RGB')
        palette_tabs = [ui.tab(cm.id) for cm in app_config.epaper_color_models]
    with ui.tab_panels(tabs, value=rgb_tab).classes('w-full'):
        with ui.tab_panel(rgb_tab):
            screen_image_view(f'{image_base_url}/{screen_id}/image.png')
        for i, tab in enumerate(palette_tabs):
            with ui.tab_panel(tab):
                screen_image_view(f'{image_base_url}/{screen_id}/image.png?color_model={color_models[i]}')

    ui.separator()

    @ui.refreshable
    def editor_area() -> None:
        if state['view'] == 'detail' and state['key'] is not None:
            _widget_detail(state['key'])
        else:
            _widget_list()

    def _widget_list() -> None:
        ui.label('Screen settings').classes('text-subtitle1')
        _render_int_pair(screen, 'size', 'Canvas size', ('Width', 'Height'), persist_screen)
        schedule_input = ui.input('Update schedule id', value=screen.update_schedule_id or '').classes('w-60')

        def _save_schedule_id() -> None:
            screen.update_schedule_id = schedule_input.value or None
            persist_screen()
        schedule_input.on('blur', lambda: _save_schedule_id())

        ui.separator()
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Widgets').classes('text-subtitle1')
            ui.button(icon='add', on_click=lambda: open_add_dialog()).props('size=sm round outline')

        widgets = list(widgets_adapter.items())
        if not widgets:
            ui.label('No widgets yet — add one above.').classes('italic')
            return

        with ui.column().classes('w-full gap-1') as widget_list_container:
            for key, widget in widgets:
                with ui.row().classes('w-full items-center border rounded-borders q-pa-sm gap-2'):
                    ui.icon('drag_indicator').classes('drag-handle cursor-move text-grey-6')
                    with ui.row().classes('items-center gap-2 flex-grow cursor-pointer').on(
                            'click', lambda _, k=key: _open_detail(k)):
                        ui.icon(WIDGET_ICONS[widget.widget_type])
                        ui.label(_widget_label(widget))
                    ui.badge(widget.widget_type).props('outline')
                    ui.button(icon='delete').props('flat dense round color=negative').on_click(
                        lambda _, k=key: _delete_widget(k))
        widget_list_container.make_sortable(handle='.drag-handle', on_end=_handle_reorder)

    def _widget_detail(key: str) -> None:
        try:
            widget = widgets_adapter.read(key)
        except (KeyError, IndexError):
            ui.notify('Widget no longer exists.', type='negative')
            _back_to_list()
            return
        model_cls = WIDGET_MODELS[widget.widget_type]

        with ui.row().classes('w-full items-center justify-between'):
            ui.button('Back to list', icon='arrow_back', on_click=lambda: _back_to_list()).props('flat')
            ui.button(icon='delete').props('color=negative dense flat').on_click(lambda: _delete_widget(key))

        ui.label(f'{widget.widget_type} widget').classes('text-h6')
        _render_int_pair(widget, 'position', 'Position', ('X', 'Y'), persist_screen)
        _render_int_pair(widget, 'size', 'Size', ('Width', 'Height'), persist_screen, allow_none=True)
        _render_font_field(widget, persist_screen)

        ui.separator()
        form = ModelForm.from_adapter(model_cls, widgets_adapter, key,
                                       exclude=['widget_type', 'position', 'size', 'font'], autosave=True)
        with ui.column().classes('w-full gap-2'):
            form.render()

    def _open_detail(key: str) -> None:
        state['view'] = 'detail'
        state['key'] = key
        editor_area.refresh()

    def _back_to_list() -> None:
        state['view'] = 'list'
        state['key'] = None
        editor_area.refresh()

    def _handle_reorder(e: SortableEventArguments) -> None:
        item = screen.widgets.pop(e.old_index)
        screen.widgets.insert(e.new_index, item)
        persist_screen()

    async def _delete_widget(key: str) -> None:
        if not await confirm_dialog('Delete widget', 'Delete this widget? This cannot be undone.',
                                     ok_label='Delete', ok_color='negative'):
            return
        widgets_adapter.delete(key)
        if state['key'] == key:
            state['view'] = 'list'
            state['key'] = None
        editor_area.refresh()
        ui.notify('Widget deleted', type='positive')

    with ui.dialog().style('width: 300px') as add_widget_dialog, ui.card():
        ui.label('Add widget').classes('text-h6')
        type_select = ui.select(list(WIDGET_MODELS), value='Text', label='Widget type').classes('w-full')
        with ui.row().classes('w-full place-content-end'):
            ui.space()
            ui.button('Cancel', on_click=lambda: add_widget_dialog.submit(None))
            ui.button('Add', on_click=lambda: add_widget_dialog.submit(type_select.value))

    async def open_add_dialog() -> None:
        widget_type = await add_widget_dialog
        if not widget_type:
            return
        new_widget = _default_widget(widget_type)
        widgets_adapter.create(new_widget)
        state['view'] = 'detail'
        state['key'] = widgets_adapter.key_from_item(new_widget)
        editor_area.refresh()

    editor_area()

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
            screen_path.unlink()
            ui.notify(f'File "{filename}" deleted.', type='positive')
            on_deleted()
        else:
            ui.notify(f'Canceled deleting "{filename}".', type='negative')


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
