"""
The project dashboard summary card nice4iot embeds on its own project page
(register_project_card('dashboard', ...) in extensions/epaper/__init__.py, which
-- unlike the other embedded cards -- requires the card to build its own
ui.card()). It looks like nice4iot's built-in cards (see docs/extensions.md in
the nice4iot repo). The per-device settings card lives in devicebinding/ui.py.
"""
import datetime
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

from nicegui import context, ui

from extensions.epaper.global_config.backend import app_config
from extensions.epaper.core.datasources.homeassistant import EntityStatus
from extensions.epaper.core.datasources.ical import IcalStatus
from extensions.epaper.core.datasources.image import ImageStatus
from extensions.epaper.core.datasources.weather import WeatherStatus
from extensions.epaper.util import humanize_age


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
    weather/Home Assistant/iCal/image caches all report the same three
    states (fine; stale but with a last-known value; nothing at all), so
    they share this -- but they keep that value in differently named fields
    (WeatherStatus.data, EntityStatus.state, IcalStatus.events,
    ImageStatus.last_update), hence `has_value` from the caller rather than
    an attribute lookup here."""
    ok_icon, bad_icon = icons
    if not status.failing:
        _health_row(ok_icon, 'positive', f'{subject}: updated {humanize_age(status.last_update, now)}', None)
        return
    tip = _failure_tooltip(status, now)
    if has_value:
        _health_row(bad_icon, 'warning',
                    f'{subject}: stale, last OK {humanize_age(status.last_update, now)}', tip)
    else:
        _health_row(bad_icon, 'negative', f'{subject}: unavailable', tip)


def dashboard_card(num_screens: int, num_schedules: int, open_url: str,
                   weather_statuses: Sequence[WeatherStatus] = (),
                   homeassistant_statuses: Sequence[EntityStatus] = (),
                   ical_statuses: Sequence[IcalStatus] = (),
                   image_statuses: Sequence[ImageStatus] = ()) -> None:
    """
    Compact always-visible summary card for nice4iot's project Dashboard
    tab. open_url is where the "open" button navigates.

    weather_statuses / homeassistant_statuses / ical_statuses / image_statuses
    (read from the respective caches by the caller) render one health line
    per location/entity/feed/source, so an outage of any datasource is
    visible here without opening a screen.
    """
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('E-Paper').classes('text-subtitle1 font-bold')
            # ui.navigate.to() would route this through nice4iot's ui.sub_pages client-side
            # router (this card lives inside it) -- which has no entry for the extension's
            # standalone page (only a real HTTP request reaches that route, in
            # nice4iot's home_page()) and shows its own 404. client.open() forces a real
            # browser navigation instead, bypassing that router.
            ui.button(icon='open_in_new').props('dense flat size=sm') \
                .tooltip(f'Dedicate Epaper UI {open_url}').on_click(lambda: context.client.open(open_url))
        ui.label(f'{num_screens} screen(s), {num_schedules} schedule(s)').classes('text-caption text-grey-7')
        for feed in ical_statuses:
            _datasource_row(feed, now, ('event_available', 'event_busy'),
                            f'iCal {feed.id}', feed.events is not None)
        for status in weather_statuses:
            _datasource_row(status, now, ('cloud_done', 'cloud_off'),
                            f'Weather {status.latitude:.2f},{status.longitude:.2f}',
                            status.data is not None)
        for entity in homeassistant_statuses:
            _datasource_row(entity, now, ('sensors', 'sensors_off'),
                            f'HA {entity.entity_id}', entity.state is not None)
        for image in image_statuses:
            _datasource_row(image, now, ('image', 'broken_image'),
                            f'Image {image.source or image.key}', image.last_update is not None)
