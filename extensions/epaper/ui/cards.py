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


def simplified_ui_link_fields(open_url: str) -> None:
    """A row linking to the simplified, room-focused UI ("Rooms & Displays
    App" -- deliberately not calling it "Simplified UI", which is this
    codebase's own internal/dev term, not a user-facing one). Content only,
    no ui.card() of its own -- used bare inside nice4iot's already-chromed
    'E-Paper' settings card (__init__.py's _settings_card), and wrapped in
    ui.card() by standalone.py's own Global tab, which supplies no chrome."""
    with ui.row().classes('w-full items-center justify-between'):
        with ui.row().classes('items-center gap-2'):
            ui.icon('meeting_room').classes('text-2xl')
            with ui.column().classes('gap-0'):
                ui.label('Rooms & Displays App').classes('text-subtitle1')
                ui.label('Room-focused view: rooms, displays, booking systems') \
                    .classes('text-caption text-grey')
        # ui.navigate.to() would route this through nice4iot's ui.sub_pages client-side
        # router (this card lives inside it) -- which has no entry for the extension's
        # standalone page (only a real HTTP request reaches that route, in
        # nice4iot's home_page()) and shows its own 404. client.open() forces a real
        # browser navigation instead, bypassing that router. Harmless in standalone too
        # (no such router there), so the same call works in both modes.
        ui.button('Open', icon='open_in_new',
                  on_click=lambda: context.client.open(open_url)).props('unelevated')


def unreadable_items_banner(count: int, subject: str) -> None:
    """Inline warning for a JSON-per-file collection that silently dropped
    N file(s) it couldn't parse -- niceview's JsonDirectoryAdapter (backing
    every list/grid in this app) and this codebase's own list_*() helpers
    both just `log.warning` and skip rather than listing a ghost, which
    means a corrupted file previously left no trace anywhere in the UI, only
    the server log. Renders nothing when count is 0, so callers can call it
    unconditionally at the top of a list view. `subject` is the plural noun,
    e.g. 'room(s)', 'screen(s)', 'booking system(s)'."""
    if not count:
        return
    with ui.row().classes('items-center gap-2 text-negative q-mb-sm'):
        ui.icon('warning').props('size=xs')
        ui.label(f'{count} {subject} failed to load and are not shown here -- check the server log.') \
            .classes('text-caption')


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


def datasource_health_rows(weather_statuses: Sequence[WeatherStatus] = (),
                           homeassistant_statuses: Sequence[EntityStatus] = (),
                           ical_statuses: Sequence[IcalStatus] = (),
                           image_statuses: Sequence[ImageStatus] = (), *,
                           only_failing: bool = False, title: Optional[str] = None) -> int:
    """One health line per cached datasource (icon/colour by severity, a
    tooltip with the last error/retry time) -- shared by dashboard_card()
    (nice4iot Dashboard tab / standalone's Project tab: every source,
    unconditionally) and the simplified UI's Rooms landing view
    (room/simplified_ui.py: `only_failing=True`, so it stays silent unless
    something is actually down -- that view has no separate Dashboard, and
    previously showed no datasource health at all).

    `title` draws a small label above the rows, but only when at least one
    row is actually drawn -- never an orphaned heading over nothing. Returns
    how many rows were drawn, so a caller that wants to react to "nothing
    failing" itself can check for 0 instead of duplicating the row logic.
    """
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    rows = [
        (feed, ('event_available', 'event_busy'), f'iCal {feed.id}', feed.events is not None)
        for feed in ical_statuses
    ] + [
        (status, ('cloud_done', 'cloud_off'),
         f'Weather {status.latitude:.2f},{status.longitude:.2f}', status.data is not None)
        for status in weather_statuses
    ] + [
        (entity, ('sensors', 'sensors_off'), f'HA {entity.entity_id}', entity.state is not None)
        for entity in homeassistant_statuses
    ] + [
        (image, ('image', 'broken_image'), f'Image {image.source or image.key}',
         image.last_update is not None)
        for image in image_statuses
    ]
    if only_failing:
        rows = [row for row in rows if row[0].failing]
    if rows and title:
        ui.label(title).classes('text-caption text-grey-7 q-mb-xs')
    for status, icons, subject, has_value in rows:
        _datasource_row(status, now, icons, subject, has_value)
    return len(rows)


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
        datasource_health_rows(weather_statuses, homeassistant_statuses, ical_statuses, image_statuses)
