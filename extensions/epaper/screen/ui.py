"""
Screen editor: the screen-level settings, the drag-reorderable widget list
that drills down into a per-widget form, and the DrillDownWrapper over
paths.screen_dir that holds them (screens_wrapper).

What a screen is made of lives elsewhere, one concern per module: the
preview image and its ruler in preview.py, everything type-specific about
a widget in widget_types.py, the file list/rename/delete chrome in
drilldown.py. What is left here is the screen itself.

screens_wrapper() owns the file-level list<->editor chrome so standalone.py
and __init__.py both just construct and render() it -- no separate
deep-linkable per-file route, since niceview's DrillDownWrapper doesn't own
routes of its own and standalone mode doesn't need one (see standalone.py).
"""
import os
from typing import Callable, Literal, Optional, TypedDict, cast

import nicegui.elements.sortable  # noqa: F401  (see below)
from nicegui import ui
from nicegui.events import SortableEventArguments
from niceview import DrillDownWrapper, Field, JsonAdapter, ListAdapter, ModelForm
from niceview.util import confirm_dialog

# NiceGUI 3.15's sortable is a mixin method (make_sortable), not a `ui.*` element,
# so nicegui's eager esm-import loop (ui.py, "Eagerly import element packages with
# 'dist' dirs") misses it: its 'nicegui-sortable' importmap entry is only
# registered on first make_sortable() call -- too late for our widget list, which
# is created dynamically after the initial page load. Importing the module here at
# setup registers the ESM eagerly so 'nicegui-sortable' is in every page's importmap.

from extensions.epaper.catalog.backend import get_palette, get_palettes, get_panel_type, get_panel_types
from extensions.epaper.catalog.models import PanelTypeModel
from extensions.epaper.screen.models import ScreenModel, WidgetModel
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.drilldown import directory_drilldown, slide_class
from extensions.epaper.ui.forms import COL, FORM_STYLE, ROW
from extensions.epaper.ui.preview import screen_image_view
from extensions.epaper.ui.widget_types import WIDGET_TYPES, new_widget, render_widget_form, widget_summary
from extensions.epaper.util import check_filename

# "no preset" is a listed choice rather than only the select's clear button:
# a screen for a panel that isn't in the catalog is a normal thing to want,
# and clearing a field is not the same as picking an option
_NO_PANEL_TYPE_LABEL = 'No preset — set size, palette and colors yourself'


class _EditorState(TypedDict):
    """The widget list<->detail navigation state (screen_editor_content()'s
    `state`): which view is shown, the open widget's key (list view only,
    None), and the slide-in direction for the next switch."""
    view: Literal['list', 'detail']
    key: Optional[str]
    direction: Literal['left', 'right']

# The Screen Settings as a niceview layout: '## Title' is a section heading
# without a card ('#' would draw one, which inside the Screen Settings
# expansion would be a card in a card), and the layout also defines *which*
# fields are rendered -- so `widgets` needs no exclude=, and an unknown or
# duplicated name raises ValueError naming its position.
_SCREEN_LAYOUT = [
    ['## Panel', COL, 'panel_type_id', [ROW, 'width', 'height', 'palette_id', 'color_background']],
    ['## Schedule', COL, 'update_schedule_id'],
]


def _panel_type_options(panel_types: dict) -> dict:
    """{panel_type_id: label} for a panel-type select, "no preset" first."""
    return {None: _NO_PANEL_TYPE_LABEL, **{p.id: p.name for p in panel_types.values()}}


def _keep_current(options, current):
    """The options with `current` added if it isn't among them.

    Each of the three selects in the screen settings points at something
    that can disappear behind the screen's back -- a panel-type preset removed
    from the catalog, a deleted palette, a deleted schedule file. Keeping
    the stored value selectable means the select shows what the screen
    actually says instead of silently dropping it (the warning below the
    schedule select then explains it)."""
    if not current or current in options:
        return options
    if isinstance(options, dict):
        return {**options, current: f'{current} (unknown)'}
    return [*options, current]


# Fields a panel-type preset fills in on apply -- the same set that must all
# still match it for panel_type_id to stay trustworthy afterward (see
# _diverges_from_panel_type(), used by on_field_change() to clear it once
# the screen has been edited past what the preset actually describes).
_PANEL_TYPE_FIELDS = ('width', 'height', 'palette_id', 'color_background')


def _apply_panel_type(screen: ScreenModel, panel_type: PanelTypeModel) -> None:
    """Copy a panel-type preset's values into a screen. One-way and one-off:
    from here on the screen's own fields are what renders, so the preset
    can be edited over, and clearing the selection later leaves the values
    it filled in place rather than resetting anything.

    Shared by the new-screen dialog and the panel-type select in the screen
    settings, so both mean exactly the same thing by 'apply a preset'."""
    screen.panel_type_id = panel_type.id
    for field in _PANEL_TYPE_FIELDS:
        setattr(screen, field, getattr(panel_type, field))


def _diverges_from_panel_type(screen: ScreenModel, panel_type: PanelTypeModel) -> bool:
    """True once any field the preset filled in no longer matches it -- the
    screen has since been edited past what panel_type_id describes, so
    on_field_change() clears it rather than let it keep naming a preset the
    screen no longer actually is."""
    return any(getattr(screen, field) != getattr(panel_type, field) for field in _PANEL_TYPE_FIELDS)


def _panel_type_hint(panel_type: Optional[PanelTypeModel]) -> Optional[str]:
    """Hint under the panel-type select: the panel's own manufacturer
    designation, for recognising a panel by the name its datasheet/firmware
    knows it under. Purely informational -- nicepaper serves a PNG and never
    drives the panel."""
    if panel_type is None or not panel_type.panel_id:
        return None
    return f'Panel: {panel_type.panel_id}'


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


def screen_editor_content(paths: EpaperPaths, filename: str, image_base_url: str,
                          render_name_field: Optional[Callable[[], None]] = None) -> None:
    """
    Screen content: the live preview and Screen Settings stay fixed; only
    the card below them (`editor_area`) swaps between the widget list and a
    widget's detail form. `image_base_url` is the display API prefix for
    this screen's images (differs between standalone and the nice4iot
    extension router). No file-level chrome (back/delete) of its own --
    that's screens_wrapper()'s job, via DrillDownWrapper's title row.

    render_name_field() is the rename field handed down by
    drilldown.directory_drilldown(). It goes into the Screen Settings, where
    the rest of what defines this screen lives -- the name is a setting of
    the screen, not chrome around it. Optional so that a caller with no
    directory behind it (the display-preset test) can render the content
    without one.

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

    # cast: screen.widgets is List[AnyWidget] (a discriminated Union of
    # WidgetModel subclasses), each member genuinely a WidgetModel -- but
    # list is invariant, so List[Union[...]] isn't List[WidgetModel] to mypy.
    widgets_adapter: ListAdapter[WidgetModel] = ListAdapter(WidgetModel, cast(list, screen.widgets))
    widgets_adapter.on_change(persist_screen)

    state: _EditorState = {'view': 'list', 'key': None, 'direction': 'right'}
    screen_id = os.path.splitext(filename)[0]
    # the geometry the preview's ruler was built for, so an edited
    # width/height (or an applied display preset) rebuilds it -- a ruler
    # labelled for the previous size would be quietly wrong
    preview_size = {'value': (screen.width, screen.height)}

    @ui.refreshable
    def image_preview() -> None:
        # one image, no tabs: the palette is a screen setting now, so
        # there is only ever one image a display would get -- and that
        # is the one worth looking at. (?raw=true still serves the
        # unquantized render for debugging, see the API docs.)
        screen_image_view(f'{image_base_url}/{screen_id}/image.png', screen.width, screen.height)

    def sync_preview() -> None:
        """Rebuild the preview only when the geometry actually changed --
        it is rebuilt from scratch, which would otherwise reset the
        auto-refresh switch on every keystroke in a color field."""
        if (screen.width, screen.height) != preview_size['value']:
            preview_size['value'] = (screen.width, screen.height)
            image_preview.refresh()

    def _select_panel_type(panel_type_id: Optional[str]) -> None:
        """Handle the panel-type select changing: applying a preset overwrites
        the fields below it, picking "no preset" only drops the record and
        leaves the size, palette and colors exactly as they are (the form
        persists panel_type_id itself)."""
        panel_type = get_panel_type(panel_type_id, paths)
        if panel_type is None:
            return
        _apply_panel_type(screen, panel_type)
        persist_screen()
        sync_preview()
        ui.notify(f'Applied {panel_type.name}', type='positive')

    @ui.refreshable
    def _screen_settings() -> None:
        def on_field_change(e) -> None:
            """One handler for the whole form: niceview passes a
            FieldChangeEventArguments, which names the field that changed
            and carries its new value. Reacting per field from here rather
            than wiring element.on('update:model-value', ...) keeps this
            independent of listener order -- and of the fact that an .on()
            handler is passed GenericEventArguments, which has no .value
            (the mistake that made picking a preset do nothing in 0.15.0)."""
            cleared_panel_type = False
            if e.field_name in _PANEL_TYPE_FIELDS and screen.panel_type_id:
                # a direct edit to one of the fields the preset filled in --
                # not _select_panel_type() applying a new one, which sets
                # them all at once and never trips this -- means the screen
                # no longer matches the preset it still names
                panel_type = get_panel_type(screen.panel_type_id, paths)
                if panel_type is not None and _diverges_from_panel_type(screen, panel_type):
                    screen.panel_type_id = None
                    cleared_panel_type = True
            persist_screen()
            sync_preview()
            if e.field_name == 'panel_type_id':
                _select_panel_type(e.value)
                _screen_settings.refresh()
            elif e.field_name == 'update_schedule_id':
                schedule_warning.refresh()
            elif cleared_panel_type:
                _screen_settings.refresh()

        # read fresh on every render of this refreshable, so a preset added
        # to the catalog or a schedule file created meanwhile shows up
        panel_types = get_panel_types(paths)
        # {id: label} rather than a plain list, so the searchable select
        # matches on the panel name the user knows while still storing the id
        panel_type_options = _keep_current(_panel_type_options(panel_types), screen.panel_type_id)
        palette_options = _keep_current(list(get_palettes(paths)), screen.palette_id)
        schedule_options = _keep_current(
            sorted(p.stem for p in paths.schedule_dir.glob('*.json')), screen.update_schedule_id)

        @ui.refreshable
        def schedule_warning() -> None:
            message = _missing_schedule_message(paths, screen.update_schedule_id)
            if message:
                ui.label(message).classes('text-caption text-negative')

        # with_input makes the select searchable -- the catalog is meant to
        # grow past what fits in a scroll list. hint is omitted rather than
        # passed as None: niceview's Field(hint=...) kwarg is typed as plain
        # str, unlike the FieldInfo it builds -- so the GxEPD2 line appears
        # only for a preset that actually names a class.
        panel_type_hint = _panel_type_hint(
            panel_types.get(screen.panel_type_id) if screen.panel_type_id else None)
        panel_type_field_kwargs = {'label': 'Panel type', 'widget_type': 'ui.select',
                                   'options': panel_type_options, 'with_input': True}
        if panel_type_hint is not None:
            panel_type_field_kwargs['hint'] = panel_type_hint

        field_infos = {
            'panel_type_id': Field(**panel_type_field_kwargs),
            'palette_id': Field(label='Palette', widget_type='ui.select', options=palette_options),
            'color_background': Field(widget_type='ui.color_input'),
            'update_schedule_id': Field(widget_type='ui.select', options=schedule_options, clearable=True),
        }

        with ui.column().classes('w-full gap-2'):
            if render_name_field is not None:
                render_name_field()
            ModelForm.from_item(screen, layout=_SCREEN_LAYOUT, field_infos=field_infos,
                                on_change=on_field_change, **FORM_STYLE).render()
            schedule_warning()

    @ui.refreshable
    def editor_area() -> None:
        with ui.column().classes(f'w-full {slide_class(state["direction"])}'):
            if state['view'] == 'detail' and state['key'] is not None:
                _widget_detail(state['key'])
            else:
                _widget_list()

    def _widget_list() -> None:
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Widgets').classes('text-subtitle1')
                ui.button(icon='add', on_click=lambda: open_add_dialog()).props('dense round size=sm').tooltip('Add a new widget')

            widgets = list(widgets_adapter.items())
            if not widgets:
                ui.label('No widgets yet — add one above.').classes('italic')
                return

            with ui.column().classes('w-full gap-1') as widget_list_container:
                for key, widget in widgets:
                    entry = WIDGET_TYPES[widget.widget_type]
                    with ui.card().tight().classes('w-full'):
                        with ui.row().classes('w-full items-center q-pa-sm gap-2'):
                            ui.icon('drag_indicator').classes('drag-handle cursor-move text-grey-6')
                            with ui.row().classes('items-center gap-2 flex-grow cursor-pointer').on(
                                    'click', lambda _, k=key: _open_detail(k)):
                                ui.icon(entry.icon)
                                ui.badge(widget.widget_type).props('outline')
                                ui.label(widget_summary(widget, paths)).classes('text-grey-8')
            widget_list_container.make_sortable(handle='.drag-handle', on_end=_handle_reorder)

    def _refresh_editor_area() -> None:
        # render_widget_form's refresh param is a plain Callable[[], None];
        # ui.refreshable's own .refresh() is typed far more loosely
        # (*args/**kwargs -> AwaitableResponse) since it's meant to accept
        # a refreshable function's own parameters -- editor_area takes none,
        # so this just narrows the call down to what's actually used.
        editor_area.refresh()

    def _widget_detail(key: str) -> None:
        try:
            widget = widgets_adapter.read(key)
        except (KeyError, IndexError):
            ui.notify('Widget no longer exists.', type='negative')
            _back_to_list()
            return

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center gap-2'):
                ui.button(icon='arrow_back').props('dense round size=sm').on_click(lambda: _back_to_list())
                ui.label(WIDGET_TYPES[widget.widget_type].title).classes('text-h6')
                ui.space()
                ui.button(icon='delete').props('dense round size=sm color=negative') \
                    .tooltip('Delete this widget') \
                    .on_click(lambda: _delete_widget(key))

            render_widget_form(widget, widgets_adapter, key, paths,
                               persist_screen, _refresh_editor_area,
                               palette=get_palette(screen.palette_id, paths))

    def _open_detail(key: str) -> None:
        state.update({'view': 'detail', 'key': key, 'direction': 'right'})
        editor_area.refresh()

    def _back_to_list() -> None:
        state.update({'view': 'list', 'key': None, 'direction': 'left'})
        editor_area.refresh()

    def _handle_reorder(e: SortableEventArguments) -> None:
        item = screen.widgets.pop(e.old_index)
        screen.widgets.insert(e.new_index, item)
        persist_screen()

    async def _delete_widget(key: str) -> None:
        if not await confirm_dialog('Delete widget', 'Delete this widget? This cannot be undone.',
                                     ok_label='Delete', ok_role='delete'):
            return
        widgets_adapter.delete(key)
        if state['key'] == key:
            state.update({'view': 'list', 'key': None, 'direction': 'left'})
        editor_area.refresh()
        ui.notify('Widget deleted', type='positive')

    with ui.dialog().style('width: 300px') as add_widget_dialog, ui.card():
        ui.label('Add widget').classes('text-h6')
        type_select = ui.select(list(WIDGET_TYPES), value='Text', label='Widget type').classes('w-full')
        with ui.row().classes('w-full place-content-end'):
            ui.space()
            ui.button('Cancel', on_click=lambda: add_widget_dialog.submit(None)).props('flat')
            ui.button('Add', on_click=lambda: add_widget_dialog.submit(type_select.value)).props('color=primary')

    async def open_add_dialog() -> None:
        widget_type = await add_widget_dialog
        if not widget_type:
            return
        widget = new_widget(widget_type)
        widgets_adapter.create(widget)
        state.update({'view': 'detail', 'key': widgets_adapter.key_from_item(widget), 'direction': 'right'})
        editor_area.refresh()

    image_preview()
    with ui.card().tight().classes('w-full'):
        with ui.expansion('Screen Settings', value=False).classes('w-full q-mb-none').props('dense header-class="text-subtitle1"'):
            _screen_settings()
    editor_area()


def screens_wrapper(paths: EpaperPaths, image_base_url: str) -> DrillDownWrapper:
    """
    Directory-backed list<->editor drill-down for screen files, shared
    verbatim by standalone.py and __init__.py -- deep-linking to a
    specific screen isn't needed, see standalone.py. All the actual
    DrillDownWrapper/DirectoryAdapter wiring lives in drilldown.
    directory_drilldown(); this just binds it to screen_dir and
    screen_editor_content, plus the one thing screens need that schedules
    don't: Add asks which panel type the new screen is for, since size and
    palette are the first decisions about a screen and every widget
    position depends on them.
    """
    panel_type_options = _panel_type_options(get_panel_types(paths))

    # what the dialog last confirmed, read by new_screen_content() below when
    # DirectoryAdapter.create() actually writes the file. Defaults to no
    # preset: picking a panel is a deliberate choice, and a preselected one
    # would be silently applied by anyone who just clicks Create.
    chosen: dict[str, Optional[str]] = {'panel_type_id': None}

    def new_screen_content() -> str:
        screen = ScreenModel(width=800, height=480)
        panel_type = get_panel_type(chosen['panel_type_id'], paths)
        if panel_type is not None:
            _apply_panel_type(screen, panel_type)
        return screen.model_dump_json(indent=2)

    with ui.dialog() as add_dialog, ui.card().style('width: 340px'):
        ui.label('New screen').classes('text-h6')
        ui.label('Optionally pick the panel this screen is for — it fills in size, '
                 'palette and colors, all editable afterwards. Without a preset the '
                 'screen starts blank at 800x480.').classes('text-caption')
        panel_type_select = ui.select(panel_type_options, value=None, label='Panel type',
                                       with_input=True).classes('w-full').props('outlined dense')
        with ui.row().classes('w-full place-content-end'):
            ui.space()
            ui.button('Cancel', on_click=lambda: add_dialog.submit(False)).props('flat')
            ui.button('Create', on_click=lambda: add_dialog.submit(True)).props('color=primary')

    async def confirm_add() -> bool:
        """Ask which panel type the new screen is for; False cancels the Add.
        Awaited inside the Add click (niceview 0.15.0), the same shape as
        the Add-widget dialog above -- dismissing the dialog is a falsy
        result, so clicking outside it cancels too."""
        if not await add_dialog:
            return False
        chosen['panel_type_id'] = panel_type_select.value
        return True

    return directory_drilldown(
        paths.screen_dir,
        default_content=new_screen_content,
        title='Screens',
        render_content=lambda filename, name_field: screen_editor_content(
            paths, filename, image_base_url, name_field),
        row_warning=lambda key: _screen_row_warning(paths, key),
        confirm_add=confirm_add,
    )
