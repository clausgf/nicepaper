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

from extensions.epaper.ui import simplified_ui


def register(app: FastAPI) -> None:
    from pathlib import Path

    from app.config import app_config as nice4iot_app_config
    from app.extensions import (
        mount_extension_router,
        register_global_card, register_project_page,
        register_device_card, register_project_card,
        register_project_tab, register_telemetry_cache_kind,
    )
    from app.paths import extension_project_dir
    from app.routes import project_extension_url

    from extensions.epaper.api.endpoints import build_extension_router
    from extensions.epaper.core.datasources.homeassistant import read_all_entity_statuses
    from extensions.epaper.core.datasources.ical import read_all_ical_statuses
    from extensions.epaper.core.datasources.image import read_all_image_statuses
    from extensions.epaper.core.datasources.weather import read_all_weather_statuses
    from extensions.epaper.global_config.backend import load_global_config, save_global_config
    from extensions.epaper.global_config.ui import global_config_fields
    from extensions.epaper.organizer.ui import organizer_names_fields
    from extensions.epaper.paths import EpaperPaths
    from extensions.epaper.project_config.ui import project_config_fields
    from extensions.epaper.bookingsystem.ui import booking_systems_wrapper
    from extensions.epaper.room.ui import rooms_wrapper
    from extensions.epaper.devicebinding.ui import device_config_card, device_dashboard_card
    from extensions.epaper.ui.cards import dashboard_card
    from extensions.epaper.schedule.ui import schedules_wrapper
    from extensions.epaper.screen.ui import screens_wrapper

    def _paths_for_project(project_name: str) -> EpaperPaths:
        root = extension_project_dir(project_name, 'epaper')
        # the project directory itself (root's parent) holds the user's image
        # files, managed via nice4iot's 'Project Files' -- see EpaperPaths
        paths = EpaperPaths(root=root, project_root=root.parent)
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
    register_project_page(simplified_ui.render)

    # esp32paper reports its active/supported panel ids as 'panel'/'panels'
    # labels on a kind='epaper' telemetry push (never 'system', which is
    # nice4iot-reserved) -- cache the latest push in the runtime sidecar
    # for O(1) reads, same mechanism as nice4iot's own 'system' snapshot.
    # See display/backend.py's _device_epaper_labels() and devicebinding/ui.py.
    register_telemetry_cache_kind('epaper')

    # --- REST -----------------------------------------------------------
    router = build_extension_router(_paths_for_project)
    mount_extension_router(app, router)

    # --- Dashboard card ---------------------------------------------------
    def _dashboard_card(project_name: str) -> None:
        paths = _paths_for_project(project_name)
        num_screens = len(list(paths.screen_dir.glob('*.json')))
        num_schedules = len(list(paths.schedule_dir.glob('*.json')))
        weather_statuses = read_all_weather_statuses(paths.weather_dir)
        homeassistant_statuses = read_all_entity_statuses(paths.homeassistant_dir)
        ical_statuses = read_all_ical_statuses(paths.ical_dir)
        image_statuses = read_all_image_statuses(paths.image_cache_dir)
        dashboard_card(num_screens, num_schedules, project_extension_url(project_name, 'epaper'),
                       weather_statuses=weather_statuses,
                       homeassistant_statuses=homeassistant_statuses,
                       ical_statuses=ical_statuses,
                       image_statuses=image_statuses)

    register_project_card('dashboard', _dashboard_card)

    # --- Settings card -------------------------------------------------
    # nice4iot renders the card chrome (foldable header, title=) for a
    # 'settings' card, unlike a project tab -- so this calls the chrome-less
    # project_config_fields(), not project_config_card() (that one's for
    # standalone.py's own Project tab, which supplies no chrome of its own).
    def _settings_card(project_name: str) -> None:
        project_config_fields(_paths_for_project(project_name))

    register_project_card('settings', _settings_card, title='E-Paper')

    # --- Organizer names card -------------------------------------------
    # Its own 'settings' card (own sidebar entry, own foldable header,
    # expanded by default like every other Project Settings section) rather
    # than a second section inside _settings_card -- register_project_card()
    # gives one section per registered card, see nice4iot's docs/extensions.md.
    # Previously simplified-UI-only (organizer/simplified_ui.py); this gives
    # it a home in the non-simplified UI too.
    def _organizer_names_card(project_name: str) -> None:
        organizer_names_fields(_paths_for_project(project_name))

    register_project_card('settings', _organizer_names_card, title='Organizer names')

    # --- Device settings card -------------------------------------------
    # Lets a device be assigned a screen and shows the resulting
    # device-specific image URL (an alias, keyed by device name, resolved
    # by the same screens/{id}/image.png route _screens_tab already uses --
    # see device_config_card()'s docstring in ui/cards.py).
    def _device_card(project_name: str, device_name: str):
        paths = _paths_for_project(project_name)
        return device_config_card(paths, project_name, device_name, f'/api/ext/epaper/{project_name}/screens')

    register_device_card('settings', _device_card, title='E-Paper')

    # --- Device dashboard card -------------------------------------------
    # esp32paper's latest kind='epaper' telemetry push (panel, panels,
    # image_status, ...) plus the same panel-type mismatch hint the
    # Settings card shows -- see devicebinding/ui.py's device_dashboard_card().
    def _device_dashboard_card(project_name: str, device_name: str):
        paths = _paths_for_project(project_name)
        return device_dashboard_card(paths, project_name, device_name)

    register_device_card('dashboard', _device_dashboard_card)

    # --- Project tabs --------------------------------------------------
    # Tabs on nice4iot's own project page (its tab bar, not ours), each
    # rendering the same DrillDownWrapper the standalone/simplified UIs use --
    # see room.ui.rooms_wrapper(), screen.ui.screens_wrapper() and
    # schedule.ui.schedules_wrapper() for the list<->editor chrome, state and
    # slide animation. Registration order is tab order: Rooms comes first.
    def _rooms_tab(project_name: str) -> None:
        rooms_wrapper(_paths_for_project(project_name), project_name).render()

    def _screens_tab(project_name: str) -> None:
        paths = _paths_for_project(project_name)
        screens_wrapper(paths, f'/api/ext/epaper/{project_name}/screens').render()

    def _schedules_tab(project_name: str) -> None:
        schedules_wrapper(_paths_for_project(project_name)).render()

    def _booking_systems_tab(project_name: str) -> None:
        booking_systems_wrapper(_paths_for_project(project_name)).render()

    register_project_tab('Rooms', _rooms_tab, icon='meeting_room')
    register_project_tab('Screens', _screens_tab, icon='wallpaper')
    register_project_tab('Schedules', _schedules_tab, icon='schedule')
    register_project_tab('Booking systems', _booking_systems_tab, icon='event')
