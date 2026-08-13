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
import math
import os
from typing import Optional

import nicegui.elements.sortable  # noqa: F401  (see below)
from nicegui import ui
from nicegui.events import SortableEventArguments
from niceview import DrillDownWrapper, JsonAdapter, ListAdapter, ModelForm
from niceview.util import confirm_dialog

# NiceGUI 3.15's sortable is a mixin method (make_sortable), not a `ui.*` element,
# so nicegui's eager esm-import loop (ui.py, "Eagerly import element packages with
# 'dist' dirs") misses it: its 'nicegui-sortable' importmap entry is only
# registered on first make_sortable() call -- too late for our widget list, which
# is created dynamically after the initial page load. Importing the module here at
# setup registers the ESM eagerly so 'nicegui-sortable' is in every page's importmap.

from extensions.epaper.catalog import get_color_models, get_display, get_displays
from extensions.epaper.config import app_config, resource_paths
from extensions.epaper.core.datasources.image import clear_cache as clear_image_cache
from extensions.epaper.models.display import DisplayModel
from extensions.epaper.models.screenmodel import (
    DateWidgetModel, HomeAssistantWidgetModel, ImageWidgetModel, RoomCalendarWidgetModel, ScreenModel,
    TextWidgetModel, WidgetModel, WeatherChartWidgetModel, WeatherForecastWidgetModel, WeatherNowWidgetModel,
    WeatherWidgetModel,
)
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.panels import (
    _DATE_PATTERN_HINT, _PATTERN_HINTS, _render_row, directory_drilldown, slide_class,
)
from extensions.epaper.util import check_filename

WIDGET_MODELS: dict[str, type[WidgetModel]] = {
    'Text': TextWidgetModel,
    'Date': DateWidgetModel,
    'RoomCalendar': RoomCalendarWidgetModel,
    'WeatherNow': WeatherNowWidgetModel,
    'WeatherForecast': WeatherForecastWidgetModel,
    'WeatherChart': WeatherChartWidgetModel,
    'Image': ImageWidgetModel,
    'HomeAssistant': HomeAssistantWidgetModel,
}
WIDGET_ICONS: dict[str, str] = {
    'Text': 'text_fields',
    'Date': 'event',
    'RoomCalendar': 'calendar_month',
    'WeatherNow': 'wb_sunny',
    'WeatherForecast': 'view_column',
    'WeatherChart': 'show_chart',
    'Image': 'image',
    'HomeAssistant': 'sensors',
}
WIDGET_TITLES: dict[str, str] = {
    'Text': 'Text Widget',
    'Date': 'Date Widget',
    'RoomCalendar': 'Room Calendar Widget',
    'WeatherNow': 'Weather (Now) Widget',
    'WeatherForecast': 'Weather (Forecast) Widget',
    'WeatherChart': 'Weather (Chart) Widget',
    'Image': 'Image Widget',
    'HomeAssistant': 'Home Assistant Widget',
}

# image files selectable by the Image widget (Pillow-readable raster formats)
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')

# Field descriptions are tooltips (niceview's default), which a touch device
# can't show. The two-letter alignment code and the Babel/CLDR format patterns
# are unusable without help, so those fields carry a compact permanent hint as
# well -- see _render_row() in panels.py.
_ALIGNMENT_HINT = 'Horizontal l/c/r + vertical t/c/b'
# the fallback is all-or-nothing (see WeatherWidgetModel.resolved_location),
# so the hint says "both", not "empty = default" per field
_LOCATION_HINTS = {
    'latitude': 'Both empty = default location',
    'longitude': 'Both empty = default location',
}

# "no preset" is a listed choice rather than only the select's clear button:
# a screen for a panel that isn't in the catalog is a normal thing to want,
# and clearing a field is not the same as picking an option
_NO_DISPLAY_LABEL = 'No preset — set size, palette and colors yourself'


def _display_options(displays: dict) -> dict:
    """{display_id: label} for a display select, "no preset" first."""
    return {None: _NO_DISPLAY_LABEL, **{d.id: d.name for d in displays.values()}}


def _location_label(widget: WeatherWidgetModel) -> str:
    """A weather widget's location for the widget list: its own
    coordinates, or a note that it follows the global default -- which is
    the one thing a bare '52.52, 13.41' could not tell apart."""
    location = widget.resolved_location(app_config.latitude, app_config.longitude)
    if location is None:
        return '(no location)'
    text = f'{location[0]:.2f}, {location[1]:.2f}'
    return text if (widget.latitude or widget.longitude) else f'{text} (default)'


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
        return f'{_location_label(widget)} · {metrics}'
    if isinstance(widget, (WeatherNowWidgetModel, WeatherForecastWidgetModel)):
        return _location_label(widget)
    if isinstance(widget, ImageWidgetModel):
        return (widget.url if widget.source_type == 'url' else widget.file) or '(no image)'
    if isinstance(widget, HomeAssistantWidgetModel):
        entity = widget.entity_id or '(no entity)'
        detail = f'.{widget.attribute}' if widget.attribute else ''
        return f'{entity}{detail} · {widget.display}'
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
    after creation.

    The placeholders are deliberately non-empty: niceview enforces required
    fields at the widget level and commits an item only once it validates as
    a whole, so a widget created with empty required strings would block
    every other edit in its form until they are filled in."""
    if widget_type == 'Text':
        return TextWidgetModel(position_x=0, position_y=0, text='Text')
    if widget_type == 'Date':
        return DateWidgetModel(position_x=0, position_y=0)
    if widget_type == 'RoomCalendar':
        return RoomCalendarWidgetModel(position_x=0, position_y=0, room_number='000', room_name='Room',
                                       ical_url='https://example.com/calendar.ics')
    if widget_type == 'Image':
        return ImageWidgetModel(position_x=0, position_y=0)
    if widget_type == 'HomeAssistant':
        return HomeAssistantWidgetModel(position_x=0, position_y=0, entity_id='sensor.example')
    if widget_type in WIDGET_MODELS and issubclass(WIDGET_MODELS[widget_type], (
            WeatherNowWidgetModel, WeatherForecastWidgetModel, WeatherChartWidgetModel)):
        # no coordinates: a new weather widget follows the default location
        # from the global settings, which beats the 0/0 in the Atlantic it
        # used to start at
        return WIDGET_MODELS[widget_type](position_x=0, position_y=0)
    raise ValueError(f'Unknown widget type: {widget_type}')


def _apply_display(screen: ScreenModel, display: DisplayModel) -> None:
    """Copy a display preset's values into a screen. One-way and one-off:
    from here on the screen's own fields are what renders, so the preset
    can be edited over, and clearing the selection later leaves the values
    it filled in place rather than resetting anything.

    Shared by the new-screen dialog and the display select in the screen
    settings, so both mean exactly the same thing by 'apply a preset'."""
    screen.display_id = display.id
    screen.width = display.width
    screen.height = display.height
    screen.color_model = display.color_model
    screen.color_background = display.color_background
    screen.color_primary = display.color_primary
    screen.color_accent = display.color_accent


def _display_hint(display: Optional[DisplayModel]) -> Optional[str]:
    """Hint under the display select: the panel's GxEPD2 class, for
    recognising a panel by the name the firmware knows it under. Purely
    informational -- nicepaper serves a PNG and never drives the panel."""
    if display is None or not display.gxepd2_class:
        return None
    return f'GxEPD2 class: {display.gxepd2_class}'


# Pixel ruler around the preview image. Grey is given as a translucent
# mid-grey rather than a theme color: it reads the same on the light and
# the dark Quasar background, so the frame needs no dark-mode variant.
# The tick marks are ::after pseudo-elements so a tick stays one element
# built from Python (a label positioned at a percentage), with the line
# itself defined once here.
#
# The child selectors are `> *`, not `> span`: NiceGUI decides the tag for
# ui.html/ui.label (both render a div), so selecting by tag silently
# matches nothing -- which drops position:absolute and stacks every tick
# in normal flow instead of spreading it along the ruler.
_RULER_CSS = '''
    .ep-preview { display: grid; grid-template-columns: 2.5rem 1fr 2.5rem;
                  grid-template-rows: 1rem auto 1rem; width: 100%; }
    .ep-canvas { position: relative; border: 1px solid rgba(128,128,128,0.55);
                 grid-column: 2; grid-row: 2; }
    .ep-ruler { position: relative; color: rgba(128,128,128,0.95);
                font-size: 0.65rem; line-height: 1; user-select: none; }
    .ep-ruler > * { position: absolute; white-space: nowrap; }
    .ep-ruler > *::after { content: ''; position: absolute; background: currentColor; }
    .ep-ruler-top    { grid-column: 2; grid-row: 1; }
    .ep-ruler-bottom { grid-column: 2; grid-row: 3; }
    .ep-ruler-left   { grid-column: 1; grid-row: 2; }
    .ep-ruler-right  { grid-column: 3; grid-row: 2; }
    .ep-ruler-top > *, .ep-ruler-bottom > * { transform: translateX(-50%); }
    .ep-ruler-left > *, .ep-ruler-right > * { transform: translateY(-50%); }
    .ep-ruler-top > *    { bottom: 4px; }
    .ep-ruler-bottom > * { top: 4px; }
    .ep-ruler-left > *   { right: 5px; }
    .ep-ruler-right > *  { left: 5px; }
    .ep-ruler-top > *::after    { left: 50%; bottom: -4px; width: 1px; height: 3px; }
    .ep-ruler-bottom > *::after { left: 50%; top: -4px; width: 1px; height: 3px; }
    .ep-ruler-left > *::after   { top: 50%; right: -5px; height: 1px; width: 3px; }
    .ep-ruler-right > *::after  { top: 50%; left: -5px; height: 1px; width: 3px; }
    .ep-readout { position: absolute; top: 4px; right: 4px; padding: 1px 5px;
                  font-size: 0.7rem; line-height: 1.3; font-variant-numeric: tabular-nums;
                  background: rgba(0,0,0,0.65); color: #fff; border-radius: 3px;
                  pointer-events: none; opacity: 0; transition: opacity 0.1s; z-index: 1; }
'''
ui.add_css(_RULER_CSS, shared=True)


def _ruler_ticks(extent: int, divisions: int = 8) -> list[int]:
    """Tick values along `extent` screen pixels: 0, step, 2*step, ... on a
    1/2/5 x 10^k step aiming for roughly `divisions` of them, so the labels
    read as round figures (100, 250, ...) rather than whatever an even
    split produces -- the same reasoning as the charts' "nice number" axis
    labels, just in CSS rather than PIL.

    The far edge is appended too (it's the number a user actually wants
    when placing something flush right/bottom), but only when it wouldn't
    crowd the last regular tick."""
    if extent <= 0:
        return [0]
    raw = extent / max(1, divisions)
    magnitude = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    # max(1, ...): below ~8 px wide the ideal step rounds to 0, and a 0 step
    # is a ValueError from range() -- i.e. a crashing editor for a screen
    # someone mistyped the width of
    step = max(1, next(int(m * magnitude) for m in (1, 2, 5, 10) if raw <= m * magnitude))

    ticks = list(range(0, extent, step))
    if extent - ticks[-1] >= step / 2:
        ticks.append(extent)
    return ticks


def _ruler_frame(url: str, width: int, height: int) -> ui.image:
    """The image inside the ruler grid; returns the ui.image so the caller
    can still force_reload() it."""
    with ui.element('div').classes('ep-preview'):
        for side, extent in (('top', width), ('bottom', width), ('left', height), ('right', height)):
            with ui.element('div').classes(f'ep-ruler ep-ruler-{side}'):
                horizontal = side in ('top', 'bottom')
                for value in _ruler_ticks(extent):
                    offset = f'{value / extent * 100:.4f}%'
                    ui.html(str(value)).style(f'{"left" if horizontal else "top"}: {offset}')

        with ui.element('div').classes('ep-canvas') as canvas:
            # the screen's aspect ratio as QImg's own `ratio`, not a CSS
            # aspect-ratio on the box: QImg reserves its height from that
            # prop before the image loads, so the side rulers line up
            # immediately and stay lined up across reloads -- while a CSS
            # ratio on the wrapper would fight QImg's own sizing (which
            # is what left the canvas empty the first time round)
            img = ui.image(url).classes('q-pa-none w-full').props(f'ratio={width / height}')
            ui.element('div').classes('ep-readout')

    # client-side only (js_handler without a Python handler emits nothing),
    # so moving the mouse doesn't send one websocket message per pixel.
    # Coordinates come from the element's own bounding box, which already
    # accounts for whatever width the browser scaled the image to.
    canvas.on('mousemove', js_handler=f'''(e) => {{
        const box = e.currentTarget.getBoundingClientRect();
        const readout = e.currentTarget.querySelector('.ep-readout');
        const clamp = (v, max) => Math.max(0, Math.min(max, v));
        const x = clamp(Math.round((e.clientX - box.left) / box.width * {width}), {width});
        const y = clamp(Math.round((e.clientY - box.top) / box.height * {height}), {height});
        readout.textContent = x + ', ' + y;
        readout.style.opacity = 1;
    }}''')
    canvas.on('mouseleave', js_handler='''(e) => {
        e.currentTarget.querySelector('.ep-readout').style.opacity = 0;
    }''')
    return img


def screen_image_view(url: str, width: int = 0, height: int = 0):
    """The rendered screen, framed by a pixel ruler.

    Widgets are positioned by typing numbers into position_x/position_y,
    so the preview is only useful if it can be read back as coordinates:
    the frame carries labelled ticks on all four sides, and moving the
    mouse over the image shows the exact pixel under the cursor.

    Ticks are placed at percentages and the canvas keeps the screen's
    aspect ratio, so the ruler stays correct at whatever width the browser
    scales the image to -- nothing here depends on the rendered size, and
    the served image itself is untouched.
    """
    if width > 0 and height > 0:
        img = _ruler_frame(url, width, height)
    else:
        # no geometry known (shouldn't happen from the editor) -- still
        # show the image rather than nothing
        img = ui.image(url).classes('q-pa-none')

    with ui.row().classes('w-full items-center no-wrap gap-1 q-pa-none'):
        # the URL takes whatever is left over and ellipsises; min-width:0 is
        # what lets a flex child shrink below its content width at all, and
        # without it the controls would be pushed off the row instead
        ui.label(f'URL: {url}').classes('italic ellipsis flex-grow') \
            .style('min-width: 0').tooltip(url)

        def toggle_boxes(e) -> None:
            # the label keeps showing the plain URL: it is there to be copied
            # into a display's configuration, and the outlines are an editor
            # view no display should ever request
            img.set_source(f'{url}?boxes=true' if e.value else url)

        ui.switch(value=False, on_change=toggle_boxes).props('dense size=sm') \
            .tooltip('Outline every widget (preview only, never sent to a display)')
        auto_refresh = ui.switch(value=True).props('dense size=sm').tooltip('Auto-Refresh')
        ui.timer(3.0, lambda: img.force_reload() if auto_refresh.value else None)
        ui.button(icon='refresh').props('round dense size=sm').on('click', lambda img=img: img.force_reload())


def screen_editor_content(paths: EpaperPaths, filename: str, image_base_url: str) -> None:
    """
    Screen content: screen-level settings, a drag-reorderable list of
    widgets that drills down into a per-type detail form, plus the live
    image preview (always on top, since it reflects whichever widget/
    setting was just edited). `image_base_url` is the display API prefix
    for this screen's images (differs between standalone and the nice4iot
    extension router). No file-level chrome (back/rename/delete) of its
    own -- that's screens_wrapper()'s job, via DrillDownWrapper's title
    row.

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

    with ui.card().tight().classes('w-full'):
        with ui.expansion('Image Preview', value=False).classes('w-full q-mb-none').props('dense header-class="text-subtitle1"'):
            image_preview()

    @ui.refreshable
    def editor_area() -> None:
        with ui.column().classes(f'w-full {slide_class(state["direction"])}'):
            if state['view'] == 'detail' and state['key'] is not None:
                _widget_detail(state['key'])
            else:
                _widget_list()

    def _select_display(display_id: Optional[str]) -> None:
        """Handle the display select changing: applying a preset overwrites
        the fields below it, picking "no preset" only drops the record and
        leaves the size, palette and colors exactly as they are (the form
        persists display_id itself)."""
        display = get_display(display_id, paths)
        if display is None:
            return
        _apply_display(screen, display)
        persist_screen()
        sync_preview()
        ui.notify(f'Applied {display.name}', type='positive')

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
            persist_screen()
            sync_preview()
            if e.field_name == 'display_id':
                _select_display(e.value)
                _screen_settings.refresh()
            elif e.field_name == 'update_schedule_id':
                schedule_warning.refresh()

        screen_form = ModelForm.from_item(screen, exclude=['widgets'], on_change=on_field_change)
        schedule_ids = _schedule_ids(paths)
        # keep a dangling current value selectable so it isn't silently
        # dropped by the select (and stays visible + flagged)
        schedule_options = schedule_ids + (
            [screen.update_schedule_id]
            if screen.update_schedule_id and screen.update_schedule_id not in schedule_ids else [])

        displays = get_displays(paths)
        # {id: label} rather than a plain list, so the searchable select
        # matches on the panel name the user knows while still storing the id
        display_options = _display_options(displays)
        if screen.display_id and screen.display_id not in display_options:
            # a preset that has since been removed: keep it visible instead
            # of silently dropping the record of what this screen was for
            display_options[screen.display_id] = f'{screen.display_id} (unknown)'
        color_model_options = list(get_color_models(paths))
        if screen.color_model and screen.color_model not in color_model_options:
            color_model_options.append(screen.color_model)

        @ui.refreshable
        def schedule_warning() -> None:
            message = _missing_schedule_message(paths, screen.update_schedule_id)
            if message:
                ui.label(message).classes('text-caption text-negative')

        with ui.column().classes('w-full gap-2'):
            ui.label('Display').classes('text-subtitle2')
            # with_input makes the select searchable -- the catalog is meant
            # to grow past what fits in a scroll list
            display_hint = _display_hint(displays.get(screen.display_id))
            screen_form.render_field(
                'display_id', label='Display', widget_type='ui.select', options=display_options,
                with_input=True, props='outlined dense',
                **({'hint': display_hint} if display_hint else {})).classes('w-full')
            _render_row(screen_form, 'width', 'height')
            screen_form.render_field(
                'color_model', widget_type='ui.select', options=color_model_options,
                props='outlined dense clearable').classes('w-full')

            ui.label('Colors').classes('text-subtitle2')
            # all three clearable: an empty field falls back to the global
            # setting, the same per-aspect override the fonts use
            with ui.row().classes('w-full gap-2'):
                for name in ('color_background', 'color_primary', 'color_accent'):
                    screen_form.render_field(name, widget_type='ui.color_input',
                                             props='outlined dense clearable').classes('flex-grow')

            ui.label('Schedule').classes('text-subtitle2')
            with ui.row().classes('w-full gap-2'):
                screen_form.render_field(
                    'update_schedule_id', widget_type='ui.select', options=schedule_options,
                    props='outlined dense clearable').classes('flex-grow')
            schedule_warning()

    def _widget_list() -> None:
        with ui.card().tight().classes('w-full'):
            with ui.expansion('Screen Settings', value=False).classes('w-full q-mb-none').props('dense header-class="text-subtitle1"'):
                _screen_settings()

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
            # only the fields rendered below appear -- ModelForm.render() is
            # never called for this form. TODO: color_primary/color_accent are
            # deliberately not rendered yet; a widget's colors are editable in
            # the screen JSON only until this form gets a color section.
            form = ModelForm.from_adapter(model_cls, widgets_adapter, key, exclude=['widget_type'], autosave=True)

            ui.label('Layout').classes('text-subtitle2')
            _render_row(form, 'position_x', 'position_y')
            _render_row(form, 'size_width', 'size_height')

            ui.label('Appearance').classes('text-subtitle2')
            _render_row(form, 'init_background', 'clipping', props='dense')
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
                form.render_field('alignment', hint=_ALIGNMENT_HINT, props='outlined dense').classes('w-40')
            elif isinstance(widget, DateWidgetModel):
                form.render_field('date_format', hint=_DATE_PATTERN_HINT,
                                  props='outlined dense').classes('w-full')
                form.render_field('alignment', hint=_ALIGNMENT_HINT, props='outlined dense').classes('w-40')
            elif isinstance(widget, RoomCalendarWidgetModel):
                _render_row(form, 'room_number', 'room_name')
                form.render_field('ical_url', props='outlined dense').classes('w-full')
                _render_row(form, 'date_format_long', 'date_format', 'time_format', hints=_PATTERN_HINTS)
            elif isinstance(widget, WeatherNowWidgetModel):
                _render_row(form, 'latitude', 'longitude', props='outlined dense clearable',
                            hints=_LOCATION_HINTS)
            elif isinstance(widget, WeatherForecastWidgetModel):
                _render_row(form, 'latitude', 'longitude', props='outlined dense clearable',
                            hints=_LOCATION_HINTS)
                _render_row(form, 'forecast_hours')
            elif isinstance(widget, WeatherChartWidgetModel):
                _render_row(form, 'latitude', 'longitude', props='outlined dense clearable',
                            hints=_LOCATION_HINTS)
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

                # no hand-written caption next to the toggle: niceview renders
                # the field's own label above widgets that have no label slot
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
            elif isinstance(widget, HomeAssistantWidgetModel):
                # only the fields that matter for the chosen display are shown
                # (gauge scale vs. text alignment), same pattern as the Image
                # widget's source_type above
                @ui.refreshable
                def display_fields() -> None:
                    if widget.display == 'gauge':
                        with ui.row().classes('w-full items-center gap-3'):
                            form.render_field('gauge_style', widget_type='ui.toggle', options=['arc', 'bar'])
                            form.render_field('min_value', props='outlined dense').classes('flex-grow')
                            form.render_field('max_value', props='outlined dense').classes('flex-grow')
                    else:
                        form.render_field('alignment', hint=_ALIGNMENT_HINT,
                                          props='outlined dense').classes('w-40')

                form.render_field('entity_id', props='outlined dense').classes('w-full')
                _render_row(form, 'attribute', 'label', 'unit')
                with ui.row().classes('w-full items-center gap-3'):
                    form.render_field('decimals', props='outlined dense').classes('w-32')
                    form.render_field('display', widget_type='ui.toggle',
                                      options=['value', 'gauge']).on(
                        'update:model-value', lambda: display_fields.refresh())
                    form.render_field('show_label', props='dense')
                display_fields()
                if not app_config.homeassistant_url:
                    ui.label('No Home Assistant URL configured — set it in the global E-Paper settings.'
                             ).classes('text-caption text-negative')
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
    drilldown(); this just binds it to screen_dir and screen_editor_content,
    plus the one thing screens need that schedules don't: Add asks which
    display the new screen is for, since size and palette are the first
    decisions about a screen and every widget position depends on them.
    """
    displays = get_displays(paths)
    display_options = _display_options(displays)

    # what the dialog last confirmed, read by default_content() below when
    # DirectoryAdapter.create() actually writes the file. Defaults to no
    # preset: picking a panel is a deliberate choice, and a preselected one
    # would be silently applied by anyone who just clicks Create.
    chosen: dict[str, Optional[str]] = {'display_id': None}

    def new_screen_content() -> str:
        screen = ScreenModel(width=800, height=480)
        display = get_display(chosen['display_id'], paths)
        if display is not None:
            _apply_display(screen, display)
        return screen.model_dump_json(indent=2)

    with ui.dialog() as add_dialog, ui.card().style('width: 340px'):
        ui.label('New screen').classes('text-h6')
        ui.label('Optionally pick the panel this screen is for — it fills in size, '
                 'palette and colors, all editable afterwards. Without a preset the '
                 'screen starts blank at 800x480.').classes('text-caption')
        display_select = ui.select(display_options, value=None, label='Display',
                                   with_input=True).classes('w-full').props('outlined dense')
        with ui.row().classes('w-full place-content-end'):
            ui.space()
            ui.button('Cancel', on_click=lambda: add_dialog.submit(False))
            ui.button('Create', on_click=lambda: add_dialog.submit(True))

    async def confirm_add() -> bool:
        """Ask which display the new screen is for; False cancels the Add.
        Awaited inside the Add click (niceview 0.15.0), the same shape as
        the Add-widget dialog above -- dismissing the dialog is a falsy
        result, so clicking outside it cancels too."""
        if not await add_dialog:
            return False
        chosen['display_id'] = display_select.value
        return True

    return directory_drilldown(
        paths.screen_dir,
        default_content=new_screen_content,
        title='Screens',
        render_content=lambda filename: screen_editor_content(paths, filename, image_base_url),
        row_warning=lambda key: _screen_row_warning(paths, key),
        confirm_add=confirm_add,
    )
