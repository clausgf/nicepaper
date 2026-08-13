"""
Content-only rendering functions shared across the screen and schedule
editors (screen_editor.py, schedule_editor.py) and the standalone/nice4iot
entry points: the global settings card, the per-device settings card, the
shared directory_drilldown() DrillDownWrapper factory, plus small helpers
(_render_row, slide_class) used by both editors. No page/route/chrome
ownership, so these work identically whether called from a standalone
@ui.page route (ui/standalone.py) or from inside nice4iot's project/device
page / card system (extensions/epaper/__init__.py's register(app)).
"""
import datetime
from pathlib import Path
from typing import Awaitable, Callable, Optional, Sequence, Union
from zoneinfo import ZoneInfo

from nicegui import context, ui
from babel.dates import format_datetime, get_timezone
from niceview import DirectoryAdapter, DrillDownWrapper, FileEntry, ModelForm

from extensions.epaper.config import app_config, resource_paths
from extensions.epaper.core.datasources.homeassistant import EntityStatus
from extensions.epaper.core.datasources.weather import WeatherStatus
from extensions.epaper.core.screen import get_aliases, set_alias
from extensions.epaper.paths import EpaperPaths
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


# Short hints for fields nobody can guess from the label alone (see
# _render_row): Babel/CLDR patterns and the '{time}' placeholder of the
# stale-data notices. The full explanation stays in the model description,
# which niceview shows as a tooltip.
_DATE_PATTERN_HINT = 'CLDR pattern, e.g. EEEE, dd. MMMM yyyy'
_SHORT_DATE_PATTERN_HINT = 'CLDR pattern, e.g. dd.MM.yy'
_TIME_PATTERN_HINT = 'CLDR pattern, e.g. HH:mm'
_PATTERN_HINTS = {
    'date_format': _SHORT_DATE_PATTERN_HINT,
    'date_format_long': _DATE_PATTERN_HINT,
    'roomcalendar_date_format_long': _DATE_PATTERN_HINT,
    'roomcalendar_date_format_short': _SHORT_DATE_PATTERN_HINT,
    'time_format': _TIME_PATTERN_HINT,
    'roomcalendar_time_format': _TIME_PATTERN_HINT,
}
_STALE_NOTICE_HINT = "'{time}' is replaced by the last successful update"
_LOCATION_HINT = 'Used by weather widgets that set no location'


def slide_class(direction: str) -> str:
    """CSS class for a slide-in-from-left/right animation, keyed by
    navigation direction ('right' when drilling into a detail view,
    'left' when going back to a list)."""
    return 'slide-in-left' if direction == 'left' else 'slide-in-right'


def _render_row(form: ModelForm, *field_names: str, props: str = 'outlined dense',
                hints: Optional[dict] = None) -> None:
    """Render several short fields side by side to save vertical space.
    Shared with screen_editor.py/schedule_editor.py (imported explicitly,
    not part of the public API of this module).

    `hints` maps a field name to a short hint rendered below its widget. Field
    descriptions are tooltips (niceview's default), which a touch device can't
    show, so fields whose value is unguessable without help — format patterns,
    alignment codes, placeholders like '{time}' — get a compact permanent hint
    on top of the full description in the tooltip."""
    hints = hints or {}
    with ui.row().classes('w-full gap-2'):
        for name in field_names:
            extra = {'hint': hints[name]} if name in hints else {}
            form.render_field(name, props=props, **extra).classes('flex-grow')


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
                         title: str, render_content: Callable[[str], None],
                         row_warning: Optional[Callable[[str], Optional[str]]] = None,
                         confirm_add: Optional[Callable[[], Awaitable[bool]]] = None) -> DrillDownWrapper:
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

    row_warning(key) is an optional, purely presentational hook: given a
    file's key (name without .json) it returns a message to show as a
    warning icon + tooltip on that list row, or None for no warning. Used by
    the screens list to flag a screen whose update_schedule_id points at a
    missing schedule file; this function stays generic and knows nothing
    about screen semantics.

    confirm_add() is an optional async hook that runs before a file is
    created and answers whether to go ahead -- e.g. by awaiting a dialog,
    as the screens list does to ask which display the new screen is for.
    Without it, Add creates the file straight away, the no-dialog style
    above. It is awaited inside the Add click (niceview 0.15.0 made
    on_add awaitable for exactly this; before that the coroutine was
    dropped silently, which is why this hook used to take a callback
    instead of returning an answer).
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
            warning = row_warning(key) if row_warning else None
            if warning:
                with ui.item_section().props('side'):
                    ui.icon('warning', color='warning').tooltip(warning)

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

    async def handle_add() -> None:
        if confirm_add is not None and not await confirm_add():
            return
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


def _humanize_age(dt: Optional[datetime.datetime], now: datetime.datetime) -> str:
    """'just now' / 'N min ago' / 'N h ago' / 'N d ago' for a past datetime."""
    if dt is None:
        return 'never'
    minutes = max(0, int((now - dt).total_seconds() // 60))
    if minutes < 1:
        return 'just now'
    if minutes < 60:
        return f'{minutes} min ago'
    if minutes < 60 * 24:
        return f'{minutes // 60} h ago'
    return f'{minutes // (60 * 24)} d ago'


def _failure_tooltip(status, now: datetime.datetime) -> str:
    """Tooltip text for a failing datasource: attempts, next retry, last error.
    Shared by the weather and Home Assistant health lines, whose status objects
    carry the same failure fields."""
    retry = ''
    if status.retry_after and status.retry_after > now:
        mins = max(1, int((status.retry_after - now).total_seconds() // 60))
        retry = f', retry in {mins} min'
    return (f'{status.fail_count} failed attempt(s){retry}'
            + (f'\nLast error: {status.error}' if status.error else ''))


def _health_row(icon: str, color: str, text: str, tip: Optional[str]) -> None:
    with ui.row().classes('items-center gap-1 no-wrap'):
        ui.icon(icon, color=color).props('size=xs')
        label = ui.label(text).classes('text-caption')
        if tip:
            label.tooltip(tip)


def _weather_status_row(status: WeatherStatus, now: datetime.datetime) -> None:
    """One dashboard health line for a weather location: colour + icon by
    severity, with a tooltip carrying the last error and retry time."""
    coord = f'{status.latitude:.2f},{status.longitude:.2f}'
    if not status.failing:
        icon, color, text, tip = 'cloud_done', 'positive', f'Weather {coord}: updated {_humanize_age(status.last_update, now)}', None
    else:
        tip = _failure_tooltip(status, now)
        if status.data is not None:
            icon, color, text = 'cloud_off', 'warning', f'Weather {coord}: stale, last OK {_humanize_age(status.last_update, now)}'
        else:
            icon, color, text = 'cloud_off', 'negative', f'Weather {coord}: unavailable'
    _health_row(icon, color, text, tip)


def _homeassistant_status_row(status: EntityStatus, now: datetime.datetime) -> None:
    """One dashboard health line per cached Home Assistant entity, same
    severity scheme as the weather lines above."""
    if not status.failing:
        icon, color, text, tip = 'sensors', 'positive', f'HA {status.entity_id}: updated {_humanize_age(status.last_update, now)}', None
    else:
        tip = _failure_tooltip(status, now)
        if status.state is not None:
            icon, color, text = 'sensors_off', 'warning', f'HA {status.entity_id}: stale, last OK {_humanize_age(status.last_update, now)}'
        else:
            icon, color, text = 'sensors_off', 'negative', f'HA {status.entity_id}: unavailable'
    _health_row(icon, color, text, tip)


def dashboard_card(num_screens: int, num_schedules: int, open_url: str,
                   weather_statuses: Sequence[WeatherStatus] = (),
                   homeassistant_statuses: Sequence[EntityStatus] = ()) -> None:
    """
    Compact always-visible summary card for nice4iot's project Dashboard
    tab (register_project_card('dashboard', ...) requires the card to
    build its own ui.card()). open_url is where the "open" button
    navigates -- resolved by the caller (project_url(project_name,
    tab='Screens')), since URL construction is nice4iot-specific and
    doesn't belong in this UI-only module.

    weather_statuses / homeassistant_statuses (read from the respective caches
    by the caller) render one health line per location/entity, so an outage of
    either datasource is visible here without opening a screen.
    """
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('E-Paper').classes('text-subtitle1 font-bold')
            ui.button(icon='open_in_new').props('flat dense round').on_click(lambda: ui.navigate.to(open_url))
        ui.label(f'{num_screens} screen(s), {num_schedules} schedule(s)').classes('text-caption text-grey-7')
        for status in weather_statuses:
            _weather_status_row(status, now)
        for entity_status in homeassistant_statuses:
            _homeassistant_status_row(entity_status, now)


async def device_config_card(paths: EpaperPaths, device_name: str, image_base_url: str) -> None:
    """
    'general' device settings card content (extensions.epaper.__init__'s
    register_device_card('general', ..., title='E-Paper') -- no
    ui.card()/ui.expansion() of its own, same nice4iot chrome contract as
    global_config_fields()).

    Lets the admin optionally assign one of the project's screens to this
    device. The assignment is stored as an ordinary alias (paths.alias_file,
    see core/screen.get_aliases()/set_alias()) keyed by the device's own
    name -- so the device-specific image URL shown below is just the
    normal screen image endpoint addressed by device name instead of
    screen id: the device only ever needs to know its own name, never any
    screen id, and every existing query parameter/header (color_model,
    If-None-Match, ...) keeps working unchanged since it's the same route.
    """
    screen_names = sorted(p.stem for p in paths.screen_dir.glob('*.json'))
    aliases = await get_aliases(paths)
    current_screen = aliases.get(device_name)

    base_url = str(context.client.request.base_url).rstrip('/')
    image_url = f'{base_url}{image_base_url}/{device_name}/image.png'

    async def on_change(e) -> None:
        await set_alias(paths, device_name, e.value)
        ui.notify('Saved', type='positive')

    ui.label('Optionally assign a screen to this device to give it its own image URL below.').classes('text-caption')
    if current_screen and current_screen not in screen_names:
        ui.label(f'Assigned screen "{current_screen}" no longer exists.').classes('text-caption text-negative')

    ui.select(
        screen_names,
        value=current_screen if current_screen in screen_names else None,
        label='Screen',
        clearable=True,
        on_change=on_change,
    ).classes('w-full').props('outlined dense')

    with ui.row().classes('w-full items-center gap-2 q-mt-sm'):
        ui.input(label='Image URL', value=image_url).props('outlined dense readonly').classes('flex-grow')
        ui.button(icon='content_copy').props('flat dense round').on_click(lambda: ui.clipboard.write(image_url))


def global_config_fields(persist: Callable[[], None]) -> None:
    """
    The GlobalConfig editing fields, no ui.card()/ui.expansion() of their
    own -- nice4iot's register_global_card('E-Paper', ...) wraps this in
    its own uniform config_expansion(title) (see docs/extensions.md in the
    nice4iot repo: 'general'/global cards must render only their fields,
    not their own chrome, so third-party cards match nice4iot's built-in
    ones). global_config_card() below adds a plain ui.card() around this
    for standalone, which has no such chrome to rely on.

    ModelForm.from_item binds directly to the shared GlobalConfig
    singleton, app_config -- not a fresh copy from an adapter -- so
    autosave edits mutate app_config's own attributes in place: every
    module that already did `from extensions.epaper.config import
    app_config` sees the changes without needing to change anything.
    `persist()` is the caller's job (write to the right JSON path for
    standalone vs. the nice4iot extension); this function doesn't know or
    care which.
    """
    font_names = sorted(p.name for p in resource_paths.font_path.glob('*') if p.is_file())
    # no exclude: every GlobalConfig field is renderable since the palette
    # catalog moved out of it (a name here that no longer exists is a hard
    # ValueError from ModelForm, which takes the whole card down)
    form = ModelForm.from_item(app_config, on_change=lambda e: persist())

    with ui.column().classes('w-full gap-2'):
        ui.label('General').classes('text-subtitle2')
        _render_row(form, 'locale', 'timezone')
        _render_row(form, 'date_format', 'time_format', hints=_PATTERN_HINTS)

        ui.label('Font & Colors').classes('text-subtitle2')
        with ui.row().classes('w-full gap-2'):
            form.render_field('font_name', widget_type='ui.select', options=font_names,
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
        _render_row(form, 'roomcalendar_date_format_long', 'roomcalendar_date_format_short',
                    'roomcalendar_time_format', hints=_PATTERN_HINTS)

        ui.label('Weather').classes('text-subtitle2')
        _render_row(form, 'latitude', 'longitude',
                    hints={'latitude': _LOCATION_HINT, 'longitude': _LOCATION_HINT})
        with ui.row().classes('w-full gap-2'):
            form.render_field('weather_update_interval_s', props='outlined dense').classes('flex-grow')
            form.render_field('wind_speed_unit', widget_type='ui.select',
                               options=['kmh', 'ms', 'mph', 'kn'],
                               props='outlined dense').classes('flex-grow')
        _render_row(form, 'weather_retry_min_s', 'weather_retry_max_s')
        _render_row(form, 'weather_error', 'weather_stale_notice',
                    hints={'weather_stale_notice': _STALE_NOTICE_HINT})

        ui.label('Image').classes('text-subtitle2')
        form.render_field('image_error', props='outlined dense').classes('w-full')

        ui.label('Home Assistant').classes('text-subtitle2')
        # explicit labels here: the humanized field names would all read
        # "Homeassistant ..." (one word, wrong spelling) and repeat the
        # section heading in every field
        form.render_field('homeassistant_url', label='Home Assistant URL',
                          props='outlined dense').classes('w-full')
        # the token is a secret: masked in the field, still stored as plain
        # text in the config file (see GlobalConfig / SECURITY.md)
        form.render_field('homeassistant_token', label='Long-lived access token',
                          props='outlined dense type=password').classes('w-full')
        with ui.row().classes('w-full gap-2'):
            form.render_field('homeassistant_update_interval_s', label='Update interval s',
                              props='outlined dense').classes('flex-grow')
            form.render_field('homeassistant_retry_min_s', label='Retry min s',
                              props='outlined dense').classes('flex-grow')
            form.render_field('homeassistant_retry_max_s', label='Retry max s',
                              props='outlined dense').classes('flex-grow')
        with ui.row().classes('w-full gap-2'):
            form.render_field('homeassistant_error', label='Error message',
                              props='outlined dense').classes('flex-grow')
            form.render_field('homeassistant_stale_notice', label='Stale notice',
                              hint=_STALE_NOTICE_HINT,
                              props='outlined dense').classes('flex-grow')

        form.render_nonfield_errors()


def global_config_card(persist: Callable[[], None]) -> None:
    """Standalone-only wrapper around global_config_fields(): standalone
    has no nice4iot chrome to supply a card/heading, so this builds its
    own -- see global_config_fields()'s docstring for why nice4iot's own
    register_global_card() usage (extensions/epaper/__init__.py) calls
    global_config_fields() directly instead of this."""
    with ui.card().classes('w-full'):
        ui.label('E-Paper Global Settings').classes('text-subtitle1')
        global_config_fields(persist)
