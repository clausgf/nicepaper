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

    from app.config import app_config as nice4iot_app_config
    from app.extensions import mount_extension_router, register_global_card, register_project_card, register_project_tab
    from app.paths import extension_project_dir
    from app.routes import project_url

    from extensions.epaper.api.endpoints import build_extension_router
    from extensions.epaper.config import load_global_config, save_global_config
    from extensions.epaper.paths import EpaperPaths
    from extensions.epaper.ui.panels import dashboard_card, global_config_fields
    from extensions.epaper.ui.schedule_editor import schedules_wrapper
    from extensions.epaper.ui.screen_editor import screens_wrapper

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
        global_config_fields(persist=lambda: save_global_config(_global_config_path))

    register_global_card('E-Paper', _global_card)

    # --- REST -----------------------------------------------------------
    router = build_extension_router(_paths_for_project)
    mount_extension_router(app, router)

    # --- Dashboard card ---------------------------------------------------
    def _dashboard_card(project_name: str) -> None:
        paths = _paths_for_project(project_name)
        num_screens = len(list(paths.screen_dir.glob('*.json')))
        num_schedules = len(list(paths.schedule_dir.glob('*.json')))
        dashboard_card(num_screens, num_schedules, project_url(project_name, tab='Screens'))

    register_project_card('dashboard', _dashboard_card)

    # --- Project tabs --------------------------------------------------
    # Two tabs on nice4iot's own project page (its tab bar, not ours),
    # each rendering the same DirectoryAdapter-backed DrillDownWrapper
    # standalone.py uses -- see screen_editor.screens_wrapper()/
    # schedule_editor.schedules_wrapper() for the list<->editor chrome,
    # state and slide animation. Nothing NiceGUI-specific left to own here.
    def _screens_tab(project_name: str) -> None:
        paths = _paths_for_project(project_name)
        screens_wrapper(paths, f'/api/ext/epaper/{project_name}/screens').render()

    def _schedules_tab(project_name: str) -> None:
        schedules_wrapper(_paths_for_project(project_name)).render()

    register_project_tab('Screens', _screens_tab)
    register_project_tab('Schedules', _schedules_tab)
