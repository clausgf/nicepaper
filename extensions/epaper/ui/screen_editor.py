"""
Screen editor: a DirectoryAdapter-backed DrillDownWrapper (screens_wrapper)
over paths.screen_dir, plus the actual screen content (screen-level
settings, the widget list/add/reorder/delete UI, and the per-widget-type
detail form) rendered inside its detail view. Split out of panels.py
(which now holds only the pieces shared across screen/schedule editors and
the standalone/extension entry points) because this is the one editor that
keeps growing as new widget types are added.

screens_wrapper() owns the file-level list<->editor chrome (title row,
Add/Rename/Delete, slide animation) so standalone.py and __init__.py both
just construct and render() it -- no separate deep-linkable per-file route,
since niceview's DrillDownWrapper doesn't own routes of its own and
standalone mode doesn't need one (see standalone.py).
"""
import os
from typing import Optional

from nicegui import ui
from nicegui.events import SortableEventArguments
from niceview import DrillDownWrapper, JsonAdapter, ListAdapter, ModelForm
from niceview.util import confirm_dialog

from extensions.epaper.config import app_config, resource_paths
from extensions.epaper.core.datasources.image import clear_cache as clear_image_cache
from extensions.epaper.models.screenmodel import (
    DateWidgetModel, ImageWidgetModel, RoomCalendarWidgetModel, ScreenModel, TextWidgetModel, WidgetModel,
    WeatherChartWidgetModel, WeatherForecastWidgetModel, WeatherNowWidgetModel,
)
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.panels import _render_row, directory_drilldown, slide_class
from extensions.epaper.util import check_filename

WIDGET_MODELS: dict[str, type[WidgetModel]] = {
    'Text': TextWidgetModel,
    'Date': DateWidgetModel,
    'RoomCalendar': RoomCalendarWidgetModel,
    'WeatherNow': WeatherNowWidgetModel,
    'WeatherForecast': WeatherForecastWidgetModel,
    'WeatherChart': WeatherChartWidgetModel,
    'Image': ImageWidgetModel,
}
WIDGET_ICONS: dict[str, str] = {
    'Text': 'text_fields',
    'Date': 'event',
    'RoomCalendar': 'calendar_month',
    'WeatherNow': 'wb_sunny',
    'WeatherForecast': 'view_column',
    'WeatherChart': 'show_chart',
    'Image': 'image',
}
WIDGET_TITLES: dict[str, str] = {
    'Text': 'Text Widget',
    'Date': 'Date Widget',
    'RoomCalendar': 'Room Calendar Widget',
    'WeatherNow': 'Weather (Now) Widget',
    'WeatherForecast': 'Weather (Forecast) Widget',
    'WeatherChart': 'Weather (Chart) Widget',
    'Image': 'Image Widget',
}

# image files selectable by the Image widget (Pillow-readable raster formats)
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')


def _widget_label(widget: WidgetModel) -> str:
    """Short label identifying a widget instance in the widget list."""
    if isinstance(widget, TextWidgetModel):
        return widget.text or '(empty text)'
    if isinstance(widget, DateWidgetModel):
        return widget.date_format or 'Date'
    if isinstance(widget, RoomCalendarWidgetModel):
        return widget.room_name or widget.room_number or '(room calendar)'
    if isinstance(widget, WeatherChartWidgetModel):
        metrics = widget.primary_metric + (f' + {widget.secondary_metric}' if widget.secondary_metric else '')
        return f'{widget.latitude:.2f}, {widget.longitude:.2f} · {metrics}'
    if isinstance(widget, (WeatherNowWidgetModel, WeatherForecastWidgetModel)):
        return f'{widget.latitude:.2f}, {widget.longitude:.2f}'
    if isinstance(widget, ImageWidgetModel):
        return (widget.url if widget.source_type == 'url' else widget.file) or '(no image)'
    return widget.widget_type


def _asset_image_files(paths: EpaperPaths) -> list[str]:
    """Image file names available in the project directory."""
    return sorted(p.name for p in paths.asset_dir.glob('*')
                  if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _schedule_ids(paths: EpaperPaths) -> list[str]:
    """Existing schedule ids (schedule file names without .json)."""
    return sorted(p.stem for p in paths.schedule_dir.glob('*.json'))


def _missing_schedule_message(paths: EpaperPaths, update_schedule_id: Optional[str]) -> Optional[str]:
    """A warning message if update_schedule_id points at a schedule file that
    doesn't exist, else None. An empty id means 'no schedule' (intentional,
    not a warning), matching get_schedule_by_id()."""
    if update_schedule_id and not (paths.schedule_dir / f'{update_schedule_id}.json').is_file():
        return f'Update schedule "{update_schedule_id}" not found — this screen won\'t be re-rendered on a schedule.'
    return None


def _screen_row_warning(paths: EpaperPaths, screen_key: str) -> Optional[str]:
    """Warning for a screen list row: flags a dangling update_schedule_id.
    Reads the screen file the same way it's loaded for rendering, so the
    effective update_schedule_id default ('default') is applied too."""
    try:
        screen = JsonAdapter(ScreenModel, paths.screen_dir / f'{screen_key}.json').read()
    except Exception:
        return None  # an unreadable/invalid screen file is a different concern
    return _missing_schedule_message(paths, screen.update_schedule_id)


def _default_widget(widget_type: str) -> WidgetModel:
    """A new widget of the given type with placeholder values for its
    required fields -- filled in by the user in the detail form right
    after creation."""
    if widget_type == 'Text':
        return TextWidgetModel(position_x=0, position_y=0, text='')
    if widget_type == 'Date':
        return DateWidgetModel(position_x=0, position_y=0)
    if widget_type == 'RoomCalendar':
        return RoomCalendarWidgetModel(position_x=0, position_y=0, room_number='', room_name='', ical_url='')
    if widget_type == 'Image':
        return ImageWidgetModel(position_x=0, position_y=0)
    if widget_type in WIDGET_MODELS and issubclass(WIDGET_MODELS[widget_type], (
            WeatherNowWidgetModel, WeatherForecastWidgetModel, WeatherChartWidgetModel)):
        return WIDGET_MODELS[widget_type](position_x=0, position_y=0, latitude=0.0, longitude=0.0)
    raise ValueError(f'Unknown widget type: {widget_type}')


def screen_image_view(url: str):
    img = ui.image(url).classes('q-pa-none')
    with ui.row().classes('w-full items-center justify-between q-pa-none'):
        truncated_url = url if len(url) <= 40 else f'...{url[-38:]}'
        ui.label(f'URL: {truncated_url}').classes('italic').tooltip(url)
        with ui.row().classes('items-center gap-1'):
            auto_refresh = ui.switch(value=True).props('dense size=sm').tooltip('Auto-Refresh')
            ui.timer(3.0, lambda: img.force_reload() if auto_refresh.value else None)
            ui.button(icon='refresh').props('round dense size=sm').on('click', lambda img=img: img.force_reload())


def screen_editor_content(paths: EpaperPaths, filename: str, image_base_url: str) -> None:
    """
    Screen content: screen-level settings, a drag-reorderable list of
    widgets that drills down into a per-type detail form, plus live
    RGB/palette image previews (always visible on top, since they reflect
    whichever widget/setting was just edited). `image_base_url` is the
    display API prefix for this screen's images (differs between
    standalone and the nice4iot extension router). No file-level chrome
    (back/rename/delete) of its own -- that's screens_wrapper()'s job,
    via DrillDownWrapper's title row.

    All edits autosave through `screen_adapter` (a single JsonAdapter for
    the whole screen file, shared by every widget below) -- widgets are a
    nested list field, not their own JSON array, so niceview's
    JsonListAdapter (which assumes the file *is* the array) doesn't apply;
    ListAdapter wraps the in-memory `screen.widgets` list instead, with
    persistence wired up via on_change().
    """
    screen_path = paths.screen_dir / filename
    if not check_filename(filename) or not screen_path.is_file():
        ui.label(f'Screen {filename!r} not found.').classes('text-negative')
        return

    screen_adapter = JsonAdapter(ScreenModel, screen_path)
    screen = screen_adapter.read()

    def persist_screen() -> None:
        screen_adapter.save(screen)

    widgets_adapter = ListAdapter(WidgetModel, screen.widgets)
    widgets_adapter.on_change(persist_screen)

    state = {'view': 'list', 'key': None, 'direction': 'right'}

    with ui.card().tight().classes('w-full'):
        with ui.expansion('Image Preview', value=False).classes('w-full q-mb-none').props('dense header-class="text-subtitle1"'):
            color_models = [cm.id for cm in app_config.epaper_color_models]
            screen_id = os.path.splitext(filename)[0]
            with ui.tabs().classes('w-full').props('dense') as tabs:
                rgb_tab = ui.tab('RGB')
                palette_tabs = [ui.tab(cm.id) for cm in app_config.epaper_color_models]
            with ui.tab_panels(tabs, value=rgb_tab).classes('w-full'):
                with ui.tab_panel(rgb_tab).style('padding: 0 !important'):
                    screen_image_view(f'{image_base_url}/{screen_id}/image.png')
                for i, tab in enumerate(palette_tabs):
                    with ui.tab_panel(tab).style('padding: 0 !important'):
                        screen_image_view(f'{image_base_url}/{screen_id}/image.png?color_model={color_models[i]}')

    @ui.refreshable
    def editor_area() -> None:
        with ui.column().classes(f'w-full {slide_class(state["direction"])}'):
            if state['view'] == 'detail' and state['key'] is not None:
                _widget_detail(state['key'])
            else:
                _widget_list()

    def _widget_list() -> None:
        with ui.card().tight().classes('w-full'):
            with ui.expansion('Screen Settings', value=False).classes('w-full q-mb-none').props('dense header-class="text-subtitle1"'):
                screen_form = ModelForm.from_item(screen, exclude=['widgets'], on_change=lambda e: persist_screen())
                schedule_ids = _schedule_ids(paths)
                # keep a dangling current value selectable so it isn't silently
                # dropped by the select (and stays visible + flagged)
                schedule_options = schedule_ids + (
                    [screen.update_schedule_id]
                    if screen.update_schedule_id and screen.update_schedule_id not in schedule_ids else [])

                @ui.refreshable
                def schedule_warning() -> None:
                    message = _missing_schedule_message(paths, screen.update_schedule_id)
                    if message:
                        ui.label(message).classes('text-caption text-negative')

                with ui.column().classes('w-full gap-2'):
                    _render_row(screen_form, 'width', 'height')
                    with ui.row().classes('w-full gap-2'):
                        screen_form.render_field(
                            'update_schedule_id', widget_type='ui.select', options=schedule_options,
                            props='outlined dense clearable').classes('flex-grow').on(
                            'update:model-value', lambda: schedule_warning.refresh())
                    schedule_warning()

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Widgets').classes('text-subtitle1')
                ui.button(icon='add', on_click=lambda: open_add_dialog()).props('size=sm round dense')

            widgets = list(widgets_adapter.items())
            if not widgets:
                ui.label('No widgets yet — add one above.').classes('italic')
                return

            with ui.column().classes('w-full gap-1') as widget_list_container:
                for key, widget in widgets:
                    with ui.card().tight().classes('w-full'):
                        with ui.row().classes('w-full items-center q-pa-sm gap-2'):
                            ui.icon('drag_indicator').classes('drag-handle cursor-move text-grey-6')
                            with ui.row().classes('items-center gap-2 flex-grow cursor-pointer').on(
                                    'click', lambda _, k=key: _open_detail(k)):
                                ui.icon(WIDGET_ICONS[widget.widget_type])
                                ui.badge(widget.widget_type).props('outline')
                                ui.label(_widget_label(widget)).classes('text-grey-8')
                            ui.button(icon='delete').props('flat dense color=negative').on_click(
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

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center gap-2'):
                ui.button(icon='arrow_back').props('round dense size=sm').on_click(lambda: _back_to_list())
                ui.label(WIDGET_TITLES[widget.widget_type]).classes('text-h6')
                ui.space()
                ui.button(icon='delete').props('round dense size=sm color=negative').on_click(lambda: _delete_widget(key))

            font_names = sorted(p.name for p in resource_paths.font_path.glob('*') if p.is_file())
            form = ModelForm.from_adapter(model_cls, widgets_adapter, key, exclude=['widget_type'], autosave=True)

            ui.label('Layout').classes('text-subtitle2')
            _render_row(form, 'position_x', 'position_y')
            _render_row(form, 'size_width', 'size_height')

            ui.label('Appearance').classes('text-subtitle2')
            _render_row(form, 'init_background', 'clipping', 'show_bounding_box', props='dense')
            # the Image widget has no text of its own, so no font to configure
            if not isinstance(widget, ImageWidgetModel):
                with ui.row().classes('w-full gap-2'):
                    # both clearable so each aspect can be reverted to the screen
                    # default independently (empty name/size falls back on its own)
                    form.render_field('font_name', widget_type='ui.select', options=font_names,
                                    props='outlined dense clearable').classes('flex-grow')
                    form.render_field('font_size', props='outlined dense clearable').classes('flex-grow')

            ui.label('Content').classes('text-subtitle2')
            if isinstance(widget, TextWidgetModel):
                form.render_field('text', props='outlined dense').classes('w-full')
                form.render_field('alignment', props='outlined dense').classes('w-32')
            elif isinstance(widget, DateWidgetModel):
                form.render_field('date_format', props='outlined dense').classes('w-full')
                form.render_field('alignment', props='outlined dense').classes('w-32')
            elif isinstance(widget, RoomCalendarWidgetModel):
                _render_row(form, 'room_number', 'room_name')
                form.render_field('ical_url', props='outlined dense').classes('w-full')
                _render_row(form, 'date_format_long', 'date_format', 'time_format')
            elif isinstance(widget, WeatherNowWidgetModel):
                _render_row(form, 'latitude', 'longitude')
            elif isinstance(widget, WeatherForecastWidgetModel):
                _render_row(form, 'latitude', 'longitude')
                _render_row(form, 'forecast_hours')
            elif isinstance(widget, WeatherChartWidgetModel):
                _render_row(form, 'latitude', 'longitude')
                _render_row(form, 'primary_metric', 'secondary_metric')
                _render_row(form, 'forecast_hours')
            elif isinstance(widget, ImageWidgetModel):
                image_files = _asset_image_files(paths)

                @ui.refreshable
                def image_source_field() -> None:
                    if widget.source_type == 'file':
                        # keep a now-missing file selectable/visible, like schedules
                        options = image_files + ([widget.file] if widget.file and widget.file not in image_files else [])
                        form.render_field('file', widget_type='ui.select', options=options,
                                          props='outlined dense clearable').classes('w-full')
                    else:
                        form.render_field('url', props='outlined dense').classes('w-full')

                with ui.row().classes('w-full items-center gap-3'):
                    ui.label('Source').classes('text-caption')
                    form.render_field('source_type', widget_type='ui.toggle',
                                      options=['url', 'file']).on(
                        'update:model-value', lambda: image_source_field.refresh())
                image_source_field()

                def _reload_image() -> None:
                    clear_image_cache(paths, widget)
                    persist_screen()  # rewrite the screen file -> re-render picks up the refetch
                    ui.notify('Image reloaded', type='positive')

                with ui.row().classes('w-full items-center gap-2'):
                    form.render_field('reload_each_time', label='Reload on every rendering', props='dense')
                    ui.space()
                    ui.button('Reload now', icon='refresh', on_click=_reload_image).props('flat dense')
            form.render_nonfield_errors()

    def _open_detail(key: str) -> None:
        state['view'] = 'detail'
        state['key'] = key
        state['direction'] = 'right'
        editor_area.refresh()

    def _back_to_list() -> None:
        state['view'] = 'list'
        state['key'] = None
        state['direction'] = 'left'
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
            state['direction'] = 'left'
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
        state['direction'] = 'right'
        editor_area.refresh()

    editor_area()


def screens_wrapper(paths: EpaperPaths, image_base_url: str) -> DrillDownWrapper:
    """
    Directory-backed list<->editor drill-down for screen files, shared
    verbatim by standalone.py and __init__.py -- deep-linking to a
    specific screen isn't needed, see standalone.py. All the actual
    DrillDownWrapper/DirectoryAdapter wiring lives in panels.directory_
    drilldown(); this just binds it to screen_dir and screen_editor_content.
    """
    return directory_drilldown(
        paths.screen_dir,
        default_content=lambda: ScreenModel(width=800, height=480).model_dump_json(indent=2),
        title='Screens',
        render_content=lambda filename: screen_editor_content(paths, filename, image_base_url),
        row_warning=lambda key: _screen_row_warning(paths, key),
    )
