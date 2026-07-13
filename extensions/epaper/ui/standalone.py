"""
Page assembly for standalone mode only: header/tabs-nav chrome and the
@ui.page routes. Never imported by the nice4iot extension entry point
(extensions/epaper/__init__.py) -- there, nice4iot owns the page chrome
and only the content functions in ui/panels.py, ui/screen_editor.py and
ui/schedule_editor.py are reused.
"""
from contextlib import contextmanager
from typing import Optional
from nicegui import ui

from extensions.epaper.config import save_global_config
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.panels import file_list, global_config_card
from extensions.epaper.ui.schedule_editor import schedule_editor
from extensions.epaper.ui.screen_editor import screen_editor

# top-level navigation: tabs, each its own route (not client-side panel
# switching), so /global, /screens and /schedules stay deep-linkable.
# Global comes first (see register_standalone_pages).
TAB_ROUTES = {'Global': '/global', 'Screens': '/screens', 'Schedules': '/schedules'}


@contextmanager
def frame(navigation_title: Optional[str] = None, active_tab: str = None):
    """Page frame to share the same styling and navigation across all pages.
    navigation_title is omitted for editor pages, which render their own
    heading (back button, filename, delete) as part of their content."""
    def on_tab_change(e):
        if e.value != active_tab:
            ui.navigate.to(TAB_ROUTES[e.value])

    with ui.header(elevated=True).style('background-color: #3874c8').classes('items-center justify-between'):
        ui.label('Epaper Doorsign Manager').classes('font-bold')
        with ui.tabs(value=active_tab, on_change=on_tab_change).props('dense indicator-color=white').classes('text-white'):
            ui.tab('Global')
            ui.tab('Screens')
            ui.tab('Schedules')
    with ui.column().classes('w-full'):
        if navigation_title:
            ui.label(navigation_title).classes('text-h5')
            ui.separator()
        yield


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
        with frame(None, 'Global'):
            global_config_card(persist=lambda: save_global_config(paths.root / "global_config.json"))

    @ui.page('/screens')
    def page_screens():
        with frame(None, 'Screens'):
            file_list(paths.screen_dir, 'screen',
                      on_select=lambda f: ui.navigate.to(f'/screens/{f}'),
                      on_add=lambda f: ui.navigate.to(f'/screens/{f}'))

    @ui.page('/screens/{filename}')
    def page_screen_edit(filename: str):
        with frame(active_tab='Screens'):
            screen_editor(paths, filename, image_base_url,
                          on_back=lambda: ui.navigate.to('/screens'),
                          on_deleted=lambda: ui.navigate.to('/screens'))

    @ui.page('/schedules')
    def page_schedules():
        with frame(None, 'Schedules'):
            file_list(paths.schedule_dir, 'schedule',
                      on_select=lambda f: ui.navigate.to(f'/schedules/{f}'),
                      on_add=lambda f: ui.navigate.to(f'/schedules/{f}'))

    @ui.page('/schedules/{filename}')
    def page_schedule_edit(filename: str):
        with frame(active_tab='Schedules'):
            schedule_editor(paths, filename,
                             on_back=lambda: ui.navigate.to('/schedules'),
                             on_deleted=lambda: ui.navigate.to('/schedules'))
