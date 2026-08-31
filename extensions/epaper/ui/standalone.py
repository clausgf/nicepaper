"""
Page assembly for standalone mode only: header/tabs-nav chrome and the
@ui.page routes. Never imported by the nice4iot extension entry point
(extensions/epaper/__init__.py) -- there, nice4iot owns the page chrome
and only the content functions (ui/cards.py, devicebinding/ui.py,
global_config/ui.py, screen/ui.py, schedule/ui.py) are reused.
"""
from contextlib import contextmanager
from nicegui import ui

from extensions.epaper.bookingsystem.ui import booking_systems_wrapper
from extensions.epaper.core.datasources.homeassistant import read_all_entity_statuses
from extensions.epaper.core.datasources.ical import read_all_ical_statuses
from extensions.epaper.core.datasources.image import read_all_image_statuses
from extensions.epaper.core.datasources.weather import read_all_weather_statuses
from extensions.epaper.devicebinding.ui import device_config_card
from extensions.epaper.global_config.backend import save_global_config
from extensions.epaper.global_config.ui import global_config_card
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.project_config.ui import project_config_card
from extensions.epaper.room.ui import rooms_wrapper
from extensions.epaper.ui import simplified_ui
from extensions.epaper.ui.cards import dashboard_card
from extensions.epaper.schedule.ui import schedules_wrapper
from extensions.epaper.screen.ui import screens_wrapper

# The simplified UI is a full page of its own (header, drawer, user menu),
# not a tab in frame(): '/simplified' renders it directly, and the Global
# tab links to it (see _simplified_ui_link / page_global below).
SIMPLIFIED_ROUTE = '/simplified'

# top-level navigation: tabs, each its own route (not client-side panel
# switching), so /global, /screens and /schedules stay deep-linkable.
# Global comes first (see register_standalone_pages). List<->editor
# switching *within* /screens and /schedules is not a separate route --
# standalone is primarily a local testing setup, not something that needs
# a bookmarkable link to one specific screen, so it uses the same
# DrillDownWrapper-based screens_wrapper()/schedules_wrapper() the nice4iot
# extension does (see __init__.py) rather than its own /screens/{filename}
# sub-route.
TAB_ROUTES = {'Global': '/global', 'Project': '/project', 'Settings': '/settings', 'Device': '/device', 'Rooms': '/rooms', 'Screens': '/screens', 'Schedules': '/schedules', 'Booking systems': '/booking-systems'}


@contextmanager
def frame(active_tab: str):
    """Page frame to share the same styling and navigation across all pages."""
    def on_tab_change(e):
        if e.value != active_tab:
            ui.navigate.to(TAB_ROUTES[e.value])

    with ui.header(elevated=True).style('background-color: #3874c8').classes('items-center justify-between'):
        ui.label('Nicepaper').classes('font-bold')
        # nicegui's own Tabs(value=...) stub only allows a Tab/TabPanel object,
        # but Quasar's QTabs (and nicegui's own on_change event value type)
        # genuinely accept selecting by the tab's name string -- this works.
        with ui.tabs(value=active_tab, on_change=on_tab_change).props('dense indicator-color=white').classes('text-white'):  # type: ignore[arg-type]
            ui.tab('Global')
            ui.tab('Project')
            ui.tab('Settings')
            ui.tab('Device')
            ui.tab('Rooms')
            ui.tab('Screens')
            ui.tab('Schedules')
            ui.tab('Booking systems')
    with ui.column().classes('w-full'):
        yield


def _simplified_ui_link() -> None:
    """Link card to the simplified, room-focused UI, shown on the Global tab
    above the settings card. The simplified UI is its own full page
    (SIMPLIFIED_ROUTE), so this only navigates there."""
    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('meeting_room').classes('text-2xl')
                with ui.column().classes('gap-0'):
                    ui.label('Simplified UI').classes('text-subtitle1')
                    ui.label('Room-focused view: rooms, displays, booking systems') \
                        .classes('text-caption text-grey')
            ui.button('Open', icon='open_in_new',
                      on_click=lambda: ui.navigate.to(SIMPLIFIED_ROUTE)).props('unelevated')


def register_standalone_pages(paths: EpaperPaths, image_base_url: str) -> None:
    """
    Register the standalone @ui.page routes. Call once, before ui.run_with().
    image_base_url is the display API's screen-image prefix, e.g.
    '/../api/screen' (see main.py).
    """

    @ui.page('/')
    def page_home():
        ui.navigate.to('/screens')

    @ui.page('/global')
    def page_global():
        with frame('Global'):
            _simplified_ui_link()
            global_config_card(persist=lambda: save_global_config(paths.root / "global_config.json"))

    @ui.page(SIMPLIFIED_ROUTE)
    @ui.page(f'{SIMPLIFIED_ROUTE}/{{_:path}}')
    def page_simplified():
        # Full-page chrome of its own -- deliberately not wrapped in frame().
        # Standalone has no project concept, so it renders the single fixed
        # root (passed in) under the name 'standalone'. Stacked with a
        # catch-all route (mirrors nice4iot's own '/ui' + '/ui/{_:path}') so
        # simplified_ui's own ui.sub_pages sub-routes (e.g. /simplified/rooms)
        # reach this same handler instead of 404ing.
        simplified_ui.render('standalone', paths=paths, image_base_url=image_base_url,
                             root_path=SIMPLIFIED_ROUTE)

    @ui.page('/project')
    def page_project():
        with frame('Project'):
            dashboard_card(num_screens=len(list(paths.screen_dir.glob('*.json'))),
                           num_schedules=len(list(paths.schedule_dir.glob('*.json'))),
                           open_url=SIMPLIFIED_ROUTE,
                           weather_statuses=read_all_weather_statuses(paths.weather_dir),
                           homeassistant_statuses=read_all_entity_statuses(paths.homeassistant_dir),
                           ical_statuses=read_all_ical_statuses(paths.ical_dir),
                           image_statuses=read_all_image_statuses(paths.image_cache_dir))

    @ui.page('/settings')
    def page_settings():
        with frame('Settings'):
            project_config_card(paths)

    @ui.page('/device')
    def page_device():
        with frame('Device'):
            device_config_card(paths, device_name='standalone', image_base_url=image_base_url)

    @ui.page('/rooms')
    def page_rooms():
        with frame('Rooms'):
            rooms_wrapper(paths, project_name='standalone').render()

    @ui.page('/screens')
    def page_screens():
        with frame('Screens'):
            screens_wrapper(paths, image_base_url).render()

    @ui.page('/schedules')
    def page_schedules():
        with frame('Schedules'):
            schedules_wrapper(paths).render()

    @ui.page('/booking-systems')
    def page_booking_systems():
        with frame('Booking systems'):
            booking_systems_wrapper(paths).render()
