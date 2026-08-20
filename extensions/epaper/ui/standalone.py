"""
Page assembly for standalone mode only: header/tabs-nav chrome and the
@ui.page routes. Never imported by the nice4iot extension entry point
(extensions/epaper/__init__.py) -- there, nice4iot owns the page chrome
and only the content functions in ui/cards.py, ui/screen_editor.py and
ui/schedule_editor.py are reused.
"""
from contextlib import contextmanager
from nicegui import ui

from extensions.epaper.config import save_global_config
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui import simplified_ui
from extensions.epaper.ui.global_settings import global_config_card
from extensions.epaper.ui.schedule_editor import schedules_wrapper
from extensions.epaper.ui.screen_editor import screens_wrapper

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
TAB_ROUTES = {'Global': '/global', 'Screens': '/screens', 'Schedules': '/schedules'}


@contextmanager
def frame(active_tab: str):
    """Page frame to share the same styling and navigation across all pages."""
    def on_tab_change(e):
        if e.value != active_tab:
            ui.navigate.to(TAB_ROUTES[e.value])

    with ui.header(elevated=True).style('background-color: #3874c8').classes('items-center justify-between'):
        ui.label('Nicepaper').classes('font-bold')
        with ui.tabs(value=active_tab, on_change=on_tab_change).props('dense indicator-color=white').classes('text-white'):
            ui.tab('Global')
            ui.tab('Screens')
            ui.tab('Schedules')
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
    def page_simplified():
        # Full-page chrome of its own -- deliberately not wrapped in frame().
        # Standalone has no project concept, so it renders the single fixed
        # root (passed in) under the name 'standalone'.
        simplified_ui.render('standalone', paths=paths)

    @ui.page('/screens')
    def page_screens():
        with frame('Screens'):
            screens_wrapper(paths, image_base_url).render()

    @ui.page('/schedules')
    def page_schedules():
        with frame('Schedules'):
            schedules_wrapper(paths).render()
