"""
nice4iot extension entry point (see nice4iot's docs/extensions.md).

All nice4iot-specific imports (app.extensions, app.paths, app.routes) are
deferred into register()'s body rather than placed at module level.
Python executes a package's __init__.py whenever any of its submodules
is imported, so a module-level "from app.paths import ..." here would
break every standalone import of extensions.epaper.* (nice4iot's own
app package doesn't exist in that process) -- register() is only ever
called by nice4iot itself, which does have app.* available.
"""
from fastapi import FastAPI


def register(app: FastAPI) -> None:
    from pathlib import Path

    from nicegui import ui

    from app.config import app_config as nice4iot_app_config
    from app.extensions import mount_extension_router, register_global_card, register_project_card, register_project_page
    from app.paths import extension_project_dir
    from app.routes import project_url

    from extensions.epaper.api.endpoints import build_extension_router
    from extensions.epaper.config import load_global_config, save_global_config
    from extensions.epaper.paths import EpaperPaths
    from extensions.epaper.ui.panels import file_list, global_config_card, slide_class
    from extensions.epaper.ui.schedule_editor import schedule_editor
    from extensions.epaper.ui.screen_editor import screen_editor

    def _paths_for_project(project_name: str) -> EpaperPaths:
        paths = EpaperPaths(root=extension_project_dir(project_name, 'epaper'))
        paths.ensure_dirs()
        return paths

    # --- Global (project-independent) config -------------------------------
    # Sibling to nice4iot's own projects_dir (e.g. data/projects ->
    # data/.epaper_global_config.json) since nice4iot has no built-in
    # helper for project-independent extension storage.
    _global_config_path = Path(nice4iot_app_config.projects_dir).parent / '.epaper_global_config.json'
    load_global_config(_global_config_path)

    def _global_card() -> None:
        global_config_card(persist=lambda: save_global_config(_global_config_path))

    register_global_card(_global_card)

    # --- REST -----------------------------------------------------------
    router = build_extension_router(_paths_for_project)
    mount_extension_router(app, router)

    # --- Dashboard card ---------------------------------------------------
    def _dashboard_card(project_name: str) -> None:
        paths = _paths_for_project(project_name)
        num_screens = len(list(paths.screen_dir.glob('*.json')))
        num_schedules = len(list(paths.schedule_dir.glob('*.json')))
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('E-Paper').classes('text-subtitle1 font-bold')
                ui.button(icon='open_in_new').props('flat dense round').on_click(
                    lambda: ui.navigate.to(f'{project_url(project_name)}/ext/epaper'))
            ui.label(f'{num_screens} screen(s), {num_schedules} schedule(s)').classes('text-caption text-grey-7')

    register_project_card('dashboard', _dashboard_card)

    # --- Standalone-within-nice4iot project page --------------------------
    # A single page (nice4iot's register_project_page allows only one):
    # Screens/Schedules as client-side tabs, list<->editor switching via
    # in-page @ui.refreshable state rather than sub-routes, since there is
    # no per-extension routing beyond this one URL.
    def _epaper_project_page(project_name: str) -> None:
        paths = _paths_for_project(project_name)
        image_base_url = f'/api/ext/epaper/{project_name}/screens'
        state = {'screen_file': None, 'schedule_file': None,
                  'screen_direction': 'right', 'schedule_direction': 'right'}

        ui.link('← Back to project', project_url(project_name)).classes('text-caption')
        ui.label('E-Paper').classes('text-h5')

        with ui.tabs().classes('w-full') as tabs:
            screens_tab = ui.tab('Screens')
            schedules_tab = ui.tab('Schedules')

        @ui.refreshable
        def screens_panel():
            with ui.column().classes(f'w-full {slide_class(state["screen_direction"])}'):
                if state['screen_file'] is None:
                    file_list(paths.screen_dir, 'screen',
                              on_select=lambda f: _select('screen_file', f),
                              on_add=lambda f: _select('screen_file', f))
                else:
                    screen_editor(paths, state['screen_file'], image_base_url,
                                  on_back=lambda: _select('screen_file', None),
                                  on_deleted=lambda: _select('screen_file', None))

        @ui.refreshable
        def schedules_panel():
            with ui.column().classes(f'w-full {slide_class(state["schedule_direction"])}'):
                if state['schedule_file'] is None:
                    file_list(paths.schedule_dir, 'schedule',
                              on_select=lambda f: _select('schedule_file', f),
                              on_add=lambda f: _select('schedule_file', f))
                else:
                    schedule_editor(paths, state['schedule_file'],
                                     on_back=lambda: _select('schedule_file', None),
                                     on_deleted=lambda: _select('schedule_file', None))

        def _select(key: str, value) -> None:
            direction_key = 'screen_direction' if key == 'screen_file' else 'schedule_direction'
            state[direction_key] = 'right' if value is not None else 'left'
            state[key] = value
            (screens_panel if key == 'screen_file' else schedules_panel).refresh()

        with ui.tab_panels(tabs, value=screens_tab).classes('w-full'):
            with ui.tab_panel(screens_tab):
                screens_panel()
            with ui.tab_panel(schedules_tab):
                schedules_panel()

    register_project_page(_epaper_project_page)
