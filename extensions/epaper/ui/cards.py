"""
The two cards nice4iot embeds in pages it owns: the project dashboard
summary and the per-device settings card.

Both render content only -- no ui.card()/ui.expansion() of their own where
nice4iot supplies one -- so they look like nice4iot's built-in cards (see
docs/extensions.md in the nice4iot repo). The dashboard card is the
exception: register_project_card('dashboard', ...) requires the card to
build its own ui.card().
"""
import datetime
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

from nicegui import context, ui

from extensions.epaper.config import app_config
from extensions.epaper.core.datasources.homeassistant import EntityStatus
from extensions.epaper.core.datasources.weather import WeatherStatus
from extensions.epaper.core.devicebinding import get_device_binding, set_device_binding
from extensions.epaper.room.backend import list_rooms
from extensions.epaper.paths import EpaperPaths


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


def _datasource_row(status, now: datetime.datetime, icons: tuple[str, str], subject: str,
                    has_value: bool) -> None:
    """One dashboard health line for a cached datasource: colour + icon by
    severity, with a tooltip carrying the last error and retry time. The
    weather and Home Assistant caches report the same three states (fine;
    stale but with a last-known value; nothing at all), so they share this
    -- but they keep that value in differently named fields
    (WeatherStatus.data, EntityStatus.state), hence `has_value` from the
    caller rather than an attribute lookup here."""
    ok_icon, bad_icon = icons
    if not status.failing:
        _health_row(ok_icon, 'positive', f'{subject}: updated {_humanize_age(status.last_update, now)}', None)
        return
    tip = _failure_tooltip(status, now)
    if has_value:
        _health_row(bad_icon, 'warning',
                    f'{subject}: stale, last OK {_humanize_age(status.last_update, now)}', tip)
    else:
        _health_row(bad_icon, 'negative', f'{subject}: unavailable', tip)


def dashboard_card(num_screens: int, num_schedules: int, open_url: str,
                   weather_statuses: Sequence[WeatherStatus] = (),
                   homeassistant_statuses: Sequence[EntityStatus] = ()) -> None:
    """
    Compact always-visible summary card for nice4iot's project Dashboard
    tab. open_url is where the "open" button navigates -- resolved by the
    caller (project_url(project_name, tab='Screens')), since URL
    construction is nice4iot-specific and doesn't belong in this UI-only
    module.

    weather_statuses / homeassistant_statuses (read from the respective caches
    by the caller) render one health line per location/entity, so an outage of
    either datasource is visible here without opening a screen.
    """
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('E-Paper').classes('text-subtitle1 font-bold')
            ui.button(icon='open_in_new').props('dense flat size=sm') \
                .tooltip('Open the screens').on_click(lambda: ui.navigate.to(open_url))
        ui.label(f'{num_screens} screen(s), {num_schedules} schedule(s)').classes('text-caption text-grey-7')
        for status in weather_statuses:
            _datasource_row(status, now, ('cloud_done', 'cloud_off'),
                            f'Weather {status.latitude:.2f},{status.longitude:.2f}',
                            status.data is not None)
        for entity in homeassistant_statuses:
            _datasource_row(entity, now, ('sensors', 'sensors_off'),
                            f'HA {entity.entity_id}', entity.state is not None)


def device_config_card(paths: EpaperPaths, device_name: str, image_base_url: str) -> None:
    """
    'general' device settings card content.

    Lets the admin assign this device a screen (the image it renders) and a
    room (where it hangs). Both are stored in the device binding
    (core/devicebinding.py) keyed by the device's own name -- so the
    device-specific image URL shown below is just the normal screen image
    endpoint addressed by device name instead of screen id: the device only
    ever needs to know its own name, never any screen id, and every existing
    query parameter/header (color_model, If-None-Match, ...) keeps working
    unchanged since it's the same route.

    The room assignment is the device->room half of the same relation the
    simplified UI reads back as "the displays in a room" (see
    core/devicebinding.devices_in_room), so a device is navigable from a room
    and vice versa.
    """
    screen_names = sorted(p.stem for p in paths.screen_dir.glob('*.json'))
    # {id: label} so the select shows the room name, not its surrogate id
    room_options = {r.id: f'{r.room_name} ({r.room_number})' for r in list_rooms(paths)}
    binding = get_device_binding(paths, device_name)

    base_url = str(context.client.request.base_url).rstrip('/')
    image_url = f'{base_url}{image_base_url}/{device_name}/image.png'

    def on_screen_change(e) -> None:
        set_device_binding(paths, device_name, screen_id=e.value)
        ui.notify('Saved', type='positive')

    def on_room_change(e) -> None:
        set_device_binding(paths, device_name, room_id=e.value)
        ui.notify('Saved', type='positive')

    ui.label('Assign a screen to this device to give it its own image URL below, '
             'and the room it is mounted in.').classes('text-caption')
    if binding.screen_id and binding.screen_id not in screen_names:
        ui.label(f'Assigned screen "{binding.screen_id}" no longer exists.').classes('text-caption text-negative')
    if binding.room_id and binding.room_id not in room_options:
        ui.label('Assigned room no longer exists.').classes('text-caption text-negative')

    ui.select(
        screen_names,
        value=binding.screen_id if binding.screen_id in screen_names else None,
        label='Screen',
        clearable=True,
        on_change=on_screen_change,
    ).classes('w-full').props('outlined dense')

    ui.select(
        room_options,
        value=binding.room_id if binding.room_id in room_options else None,
        label='Room',
        clearable=True,
        on_change=on_room_change,
    ).classes('w-full').props('outlined dense')

    with ui.row().classes('w-full items-center gap-2 q-mt-sm'):
        ui.input(label='Image URL', value=image_url).props('outlined dense readonly').classes('flex-grow')
        ui.button(icon='content_copy').props('dense flat') \
            .tooltip('Copy the URL').on_click(lambda: ui.clipboard.write(image_url))
