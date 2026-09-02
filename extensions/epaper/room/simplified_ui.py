"""
Rooms section: a niceview DrillDownWrapper over the rooms directory
(rooms_adapter, a JsonDirectoryAdapter), so the list, Add and Delete are
niceview's; this module only supplies the row and the detail body -- three
tabs: Occupancy (free/occupied status, next meeting, upcoming events -- from
the room's booking system, plus the room's photo at the bottom, see
_occupancy_panel()), Settings (the RoomModel form, autosaving through the
adapter, plus the photo upload/remove, see _settings_panel()), and Displays
(a room summary, the photo, then a drill-down list of the devices bound to
the room, see _displays_panel()).

The form's field metadata (labels/widgets/hints) lives on RoomModel itself
(its fields' Annotated FieldInfo); only the visual layout is here.

The photo itself is not a RoomModel field -- it's a plain file in
EpaperPaths.room_photo_dir, extension-owned rather than the user's project
directory (see room/photo.py); _room_photo_view() renders it, capped so it
can't dominate a tab on a phone.
"""
import datetime
from typing import Any, Optional, cast
from zoneinfo import ZoneInfo

from babel.dates import format_datetime
from nicegui import background_tasks, core, events, ui
from niceview import CollectionAdapter, DrillDownWrapper, ModelForm
import niceview

from extensions.epaper.bookingsystem.backend import list_booking_systems
from extensions.epaper.catalog.backend import get_panel_types, panel_type_label
from extensions.epaper.core.datasources.homeassistant import read_all_entity_statuses
from extensions.epaper.core.datasources.ical import read_all_ical_statuses
from extensions.epaper.core.datasources.image import read_all_image_statuses
from extensions.epaper.core.datasources.weather import read_all_weather_statuses
from extensions.epaper.devicebinding.backend import set_device_binding
from extensions.epaper.display.backend import (
    RoomDisplaysAdapter, assignable_devices, available_screen_ids, panel_mismatch_hint,
    project_device_names,
)
from extensions.epaper.display.models import RoomDisplayRow
from extensions.epaper.display.preview import render_device_preview
from extensions.epaper.global_config.backend import app_config
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.room.backend import (
    count_unreadable_rooms, get_room_events, read_room, rooms_adapter,
)
from extensions.epaper.room.models import ROOM_TYPE_LABELS, RoomModel
from extensions.epaper.room.photo import delete_room_photo, room_photo_path, save_room_photo

from extensions.epaper.ui.cards import datasource_health_rows, unreadable_items_banner
from extensions.epaper.ui.simplified_ui.layout import Shell


def render_rooms(shell: Shell, room_id: Optional[str] = None) -> None:
    """room_id, when given (the /rooms/{room_id} deep link, see
    ui/simplified_ui/__init__.py), opens straight to that room's detail
    instead of the list. An unknown id falls back to DrillDownWrapper's own
    "not found" label.

    Sets the wrapper's initial state directly rather than calling its public
    open() after render(): open() is meant for an already-rendered wrapper
    (e.g. a click handler) and refreshes its body accordingly, which needs a
    running event loop -- here we know the detail view from the start, so
    building straight into it avoids that refresh entirely.

    On the plain list (room_id is None, the app's landing view) a quiet
    datasource-outage summary sits above the list -- see
    ui.cards.datasource_health_rows(only_failing=True). Unlike nice4iot's own
    Dashboard/standalone's Project tab, the simplified UI otherwise shows no
    weather/Home Assistant/iCal/image health at all. Same spot: a warning if
    any room file failed to parse and was silently dropped from the list
    (ui.cards.unreadable_items_banner(), room.backend.count_unreadable_rooms())."""
    if room_id is None:
        _datasource_health_summary(shell.paths)
        unreadable_items_banner(count_unreadable_rooms(shell.paths), 'room(s)')
    adapter = rooms_adapter(shell.paths)
    wrapper = DrillDownWrapper(
        RoomModel, adapter,  # list title/description come from RoomModel.Meta
        item_title_field='room_label',
        item_subtitle_fields=['room_type', 'capacity'],
        render_detail=lambda a, key, set_key: _render_detail(shell, a, key),
    )
    if room_id is not None:
        wrapper._state.update(view='detail', key=room_id, animate=False)
    wrapper.render()


def _datasource_health_summary(paths: EpaperPaths) -> None:
    """Quiet outage summary above the Rooms list: nothing when every
    datasource is fine, one line per failing one otherwise -- see
    ui.cards.datasource_health_rows()."""
    datasource_health_rows(
        weather_statuses=read_all_weather_statuses(paths.weather_dir),
        homeassistant_statuses=read_all_entity_statuses(paths.homeassistant_dir),
        ical_statuses=read_all_ical_statuses(paths.ical_dir),
        image_statuses=read_all_image_statuses(paths.image_cache_dir),
        only_failing=True, title='Data source issues',
    )


def _render_detail(shell: Shell, adapter: CollectionAdapter[RoomModel], key: str) -> None:
    room = adapter.read(key)
    with ui.tabs().classes('w-full') as tabs:
        ui.tab('occupancy', label='Occupancy', icon='event_available')
        ui.tab('settings', label='Settings', icon='tune')
        ui.tab('displays', label='Displays', icon='tv')
    with ui.tab_panels(tabs, value='occupancy').classes('w-full'):
        with ui.tab_panel('occupancy'):
            _occupancy_panel(shell, room)
        with ui.tab_panel('settings'):
            _settings_panel(shell, adapter, key, room)
        with ui.tab_panel('displays'):
            _displays_panel(shell, key)


def _room_photo_view(paths: EpaperPaths, room_id: str) -> None:
    """The room's photo, if it has one -- capped height so it can't dominate
    a tab on a phone, cropped (not squeezed) to fill the width."""
    path = room_photo_path(paths, room_id)
    if path is None:
        return
    ui.image(path).classes('w-full rounded-borders').props('fit=cover height=192px')


def _settings_panel(shell: Shell, adapter: CollectionAdapter[RoomModel], key: str, room: RoomModel) -> None:
    """The RoomModel form (field_infos come from RoomModel's Annotated
    FieldInfo; only the layout and the runtime-dependent booking-system
    options are supplied here, shared with the project-tab editor,
    room/ui.py; autosaves through the adapter), plus the room's photo below
    it -- view, upload (replaces any previous one) and remove."""
    ModelForm.from_adapter(RoomModel, adapter, key, autosave=True,
                           field_infos=booking_system_field_infos(shell.paths, room),
                           ).render()

    @ui.refreshable
    def photo_section() -> None:
        ui.label('Photo').classes('text-subtitle2 q-mt-md')
        has_photo = room_photo_path(shell.paths, key) is not None
        _room_photo_view(shell.paths, key)

        async def handle_upload(e: events.UploadEventArguments) -> None:
            try:
                save_room_photo(shell.paths, key, e.file.name, await e.file.read())
            except ValueError as exc:
                ui.notify(str(exc), type='negative')
                return
            photo_section.refresh()

        def handle_remove() -> None:
            delete_room_photo(shell.paths, key)
            photo_section.refresh()

        with ui.row().classes('w-full items-center gap-2'):
            ui.upload(on_upload=handle_upload, auto_upload=True) \
                .props('accept=image/* flat dense').classes('max-w-xs')
            if has_photo:
                ui.button('Remove photo', icon='delete', on_click=handle_remove) \
                    .props('flat dense color=negative')

    photo_section()


def _occupancy_panel(shell: Shell, room: RoomModel) -> None:
    """Live occupancy: a free/occupied-until status card, then a list of
    every upcoming event -- both from the room's booking system (see
    RoomModel.booking_system_id, room/backend.py's get_room_events()). The
    fetch is async (a network call), so this renders a loading state first
    and refreshes once it lands; background_tasks.create (not a bare
    asyncio.create_task) keeps the task bound to this page's client so the
    refresh actually reaches the browser.

    The reload button bypasses the iCal cache (get_room_events(force=True))
    for cases the cache's own TTL/backoff wouldn't catch, e.g. a booking made
    after the last fetch that should show up now, not after update_interval
    elapses on its own.

    The room's photo (if any), below everything else -- see
    _room_photo_view()."""
    state: dict[str, Any] = {'events': None, 'error': None}

    @ui.refreshable
    def body() -> None:
        with ui.row().classes('w-full items-center justify-end'):
            ui.button(icon='refresh').props('dense round size=sm flat') \
                .tooltip('Reload from booking system').on_click(reload)
        if state['error'] is not None:
            with ui.row().classes('items-center gap-2 text-grey'):
                ui.icon('info').props('size=xs')
                ui.label(state['error'])
            return
        if state['events'] is None:
            with ui.row().classes('items-center gap-2'):
                ui.spinner()
                ui.label('Loading calendar…')
            return
        _occupancy_status(state['events'])
        _occupancy_upcoming(state['events'])

    async def load(force: bool = False) -> None:
        try:
            state['events'] = await get_room_events(shell.paths, room, force=force)
            state['error'] = None
        except Exception as exc:
            state['error'] = str(exc)
        body.refresh()

    async def reload() -> None:
        state['events'] = None
        state['error'] = None
        body.refresh()
        await load(force=True)

    body()
    if core.loop is not None:  # no running nicegui app -- e.g. a render test building the tree only
        background_tasks.create(load(), name=f'occupancy-{room.id}')
    _room_photo_view(shell.paths, room.id)


def _event_time(iso: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(iso)


def _fmt_time(iso: str) -> str:
    return format_datetime(_event_time(iso), format=app_config.roomcalendar_time_format,
                           tzinfo=ZoneInfo(app_config.timezone), locale=app_config.locale)


def _fmt_date(iso: str) -> str:
    return format_datetime(_event_time(iso), format=app_config.roomcalendar_date_format_short,
                           tzinfo=ZoneInfo(app_config.timezone), locale=app_config.locale)


def _occupancy_status(events: list) -> None:
    """Free, or occupied until the current event ends; below that, when the
    next meeting today starts (the current one's own end, if occupied)."""
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    current = next((e for e in events if _event_time(e['dtstart']) <= now < _event_time(e['dtend'])), None)
    today_ahead = [e for e in events if _event_time(e['dtstart']) > now
                  and _event_time(e['dtstart']).date() == now.date()]

    with ui.card().classes('w-full items-center gap-1 p-6'):
        if current is not None:
            ui.icon('event_busy').classes('text-6xl text-negative')
            ui.label('Occupied').classes('text-h5')
            ui.label(f"Until {_fmt_time(current['dtend'])}").classes('text-subtitle1 text-grey')
        else:
            ui.icon('event_available').classes('text-6xl text-positive')
            ui.label('Free').classes('text-h5')
        if today_ahead:
            nxt = today_ahead[0]
            label = 'Next' if current is None else 'Then'
            ui.label(f"{label}: {_fmt_time(nxt['dtstart'])}–{_fmt_time(nxt['dtend'])} {nxt['summary']}") \
                .classes('text-caption text-grey')
        elif current is None:
            ui.label('No more meetings today').classes('text-caption text-grey')


def _occupancy_upcoming(events: list) -> None:
    ui.label('Upcoming').classes('text-subtitle1 q-mt-md')
    if not events:
        ui.label('No upcoming appointments.').classes('italic text-grey')
        return
    with ui.list().props('bordered separator').classes('w-full'):
        for e in events:
            with ui.item():
                with ui.item_section():
                    ui.item_label(e['summary'])
                    subtitle = f"{_fmt_date(e['dtstart'])} {_fmt_time(e['dtstart'])}–{_fmt_time(e['dtend'])}"
                    if e['organizer']:
                        subtitle += f" · {e['organizer']}"
                    ui.item_label(subtitle).props('caption')


def _room_summary(room: RoomModel) -> None:
    """Compact room header for the Displays tab: label + type, and, smaller,
    building/floor -- so the room is identifiable without switching tabs."""
    with ui.column().classes('w-full gap-0 q-mb-md'):
        room_type_label = ROOM_TYPE_LABELS.get(room.room_type, room.room_type)
        ui.label(f'{room.room_label} · {room_type_label}').classes('text-subtitle1')
        location = ', '.join(v for v in (room.building, room.floor) if v)
        if location:
            ui.label(location).classes('text-caption text-grey')


def _displays_panel(shell: Shell, room_id: str) -> None:
    """The displays in this room: a room header, its photo (if any, see
    _room_photo_view()), then a drill-down list of the devices bound to it
    (Title device name, Subtitle screen/panel/firmware -- panel is
    display_rows()'s panel_label, "{panel_id} {name}" suffixed with a "⚠"
    glyph when it doesn't match what the firmware itself reports, see
    display.backend.panel_mismatch_hint()), each editable (its Screen) and
    deletable (unassigns it from the room). Add picks from the project's
    assignable devices -- there is nothing to type, so the wrapper's standard
    Add button drives a device picker instead of an empty new item."""
    room = read_room(shell.paths, room_id)
    if room is None:
        ui.label('Room not found.').classes('text-negative')
        return
    _room_summary(room)
    _room_photo_view(shell.paths, room_id)

    adapter = RoomDisplaysAdapter(shell.paths, shell.project_name, room_id)

    async def handle_add() -> None:
        names = assignable_devices(shell.paths, shell.project_name, room_id)
        if not names:
            ui.notify('No assignable devices — provision one in nice4iot first.', type='warning')
            return
        with ui.dialog() as dialog, ui.card().classes('min-w-72 gap-2'):
            ui.label('Add display to this room').classes('text-subtitle1')
            select = ui.select(names, label='Device').classes('w-full')
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=lambda: dialog.submit(None)).props('flat')
                ui.button('Add', on_click=lambda: dialog.submit(select.value)).props('unelevated')
        device_name = await dialog
        if not device_name:
            return
        adapter.create(RoomDisplayRow(device_name=device_name))
        wrapper.open(device_name)

    wrapper = DrillDownWrapper(
        RoomDisplayRow, adapter,
        title='Displays',
        item_title_field='device_name',
        item_subtitle_fields=['screen_label', 'panel_label', 'firmware_version'],
        on_add=handle_add,
        # cast: DrillDownWrapper's render_detail is typed over the generic
        # CollectionAdapter protocol, but it always calls back with the exact
        # adapter instance given to the constructor above -- a RoomDisplaysAdapter,
        # whose rename() (used below for the Device select) isn't part of that
        # protocol.
        render_detail=lambda a, key, set_key: _display_detail(
            shell, cast(RoomDisplaysAdapter, a), key, set_key),
    )
    wrapper.render()


def _display_detail(shell: Shell, adapter: RoomDisplaysAdapter, key: str, set_key) -> None:
    """A bound device's own detail: Device (editable -- reassigns this row to
    a different nice4iot device, keeping the same room/screen; a plain select
    for now, over every project device -- see project_device_names()), Panel
    type (editable, restricts Screen to matching resolution/palette and
    drives the mismatch hint against what the firmware itself reports --
    display.backend.panel_mismatch_hint()) and Screen (editable, likewise a
    plain select over the project's screen files for now -- TODO: once
    screens carry a richer label, e.g. panel_label, show that instead of the
    bare id). Delete (unassign from the room) is the wrapper's standard
    chrome.

    Device identifies the row (RoomDisplaysAdapter keys by device name), so
    changing it needs an explicit rename + set_key -- like the file editors'
    Name field (ui/drilldown.py) -- rather than the model form's normal
    autosave, which only ever updates in place under the key it was opened
    with. The body is a local @ui.refreshable so it can redraw itself
    against the new key once the rename actually lands.

    Below the settings, render_device_preview() (display/preview.py) adds
    Current/Last delivered tabs showing the actual rendered screen.
    """
    paths, project_name = shell.paths, shell.project_name

    @ui.refreshable
    def body(current_key: str) -> None:
        row = adapter.read(current_key)
        device_names = project_device_names(project_name)
        if row.device_name not in device_names:
            device_names = [row.device_name, *device_names]  # keep a since-removed device selectable

        def on_device_change(e) -> None:
            try:
                new_key = adapter.rename(current_key, e.value)
            except (KeyError, ValueError) as exc:
                ui.notify(str(exc), type='negative')
                return
            set_key(new_key)
            body.refresh(new_key)

        ui.select(device_names, value=row.device_name, label='Device',
                 on_change=on_device_change).classes('w-full').props('outlined dense')

        panel_types = get_panel_types(paths)
        panel_type_options = {pt.id: panel_type_label(pt) for pt in panel_types.values()}

        def on_panel_type_change(e) -> None:
            set_device_binding(paths, current_key, panel_type_id=e.value)
            body.refresh(current_key)

        ui.select(
            panel_type_options,
            value=row.panel_type_id if row.panel_type_id in panel_type_options else None,
            label='Panel type',
            clearable=True,
            on_change=on_panel_type_change,
        ).classes('w-full').props('outlined dense')

        mismatch_hint = panel_mismatch_hint(paths, panel_types, row.panel_type_id, row.reported_panel)
        if mismatch_hint:
            ui.label(mismatch_hint).classes('text-caption text-negative')

        # filtered to the device's own panel type if it has one set -- see
        # display.backend.available_screen_ids(). an empty options list
        # crashes the select widget, so fall back to a plain hinted field
        # rather than passing one -- same rule as booking_system_field_infos()
        # below.
        screen_ids = available_screen_ids(paths, current_key)
        screen_field = (niceview.Field(widget_type='ui.select', options=screen_ids, clearable=True)
                       if screen_ids else niceview.Field(hint='No screens yet — add one in Templates'))
        ModelForm.from_adapter(RoomDisplayRow, adapter, current_key, autosave=True,
                               include=['screen_id'],
                               field_infos={'screen_id': screen_field},
                               ).render()

        render_device_preview(paths, current_key, row.screen_id, shell.image_base_url)

    body(key)


def booking_system_field_infos(paths: EpaperPaths, room: RoomModel) -> dict:
    """Make booking_system_id a select of the configured systems ({id: name}).
    The options are runtime data, so they can't live on the model; passed here
    they merge over the model's FieldInfo. A stored-but-deleted system stays
    visible (like the screen editor keeps a dangling schedule selectable); with
    no systems yet the field falls back to a plain, hinted input."""
    options = {s.id: s.name for s in list_booking_systems(paths)}
    current = room.booking_system_id
    if current and current not in options:
        options = {**options, current: f'{current} (unknown)'}
    if options:
        return {'booking_system_id': niceview.Field(
            widget_type='ui.select', options=options, clearable=True)}
    return {'booking_system_id': niceview.Field(
        hint='No booking systems yet — add one in Settings')}
