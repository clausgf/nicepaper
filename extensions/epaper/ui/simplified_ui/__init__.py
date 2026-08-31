"""
Simplified UI: a room-focused, e-paper-only alternative to the standalone/
nice4iot editors, rendered as the extension's standalone project page
(register_project_page in extensions/epaper/__init__.py).

`render(project_name)` is the entry point nice4iot calls. It defines the
sidebar navigation and hands off to layout.build_page(); every section's
content lives in its own module (rooms, templates/screens, displays, booking).
"""
from typing import Any, Callable, Optional

from extensions.epaper.paths import EpaperPaths

from extensions.epaper.bookingsystem.simplified_ui import render_booking_systems
from extensions.epaper.global_config.simplified_ui import render_global_settings
from extensions.epaper.organizer.simplified_ui import render_organizer_names
from extensions.epaper.project_config.simplified_ui import render_project_settings
from extensions.epaper.room.simplified_ui import render_rooms
from extensions.epaper.schedule.simplified_ui import render_schedule
from extensions.epaper.screen.simplified_ui import render_templates

from extensions.epaper.display.simplified_ui import render_displays
from .layout import NavItem, Shell, build_page


def _paths_for_project(project_name: str) -> EpaperPaths:
    """The project's EpaperPaths when running as a nice4iot extension.

    Deferred `app.*` import: it exists only inside the nice4iot process.
    Standalone passes its own paths to render() instead, so this is never
    reached there. Mirrors extensions/epaper/__init__.py's _paths_for_project.
    """
    from app.paths import extension_project_dir
    root = extension_project_dir(project_name, 'epaper')
    paths = EpaperPaths(root=root, project_root=root.parent)
    paths.ensure_dirs()
    return paths


def _nav() -> list[NavItem]:
    """Two-level sidebar: leaf sections plus a Settings group.

    The first leaf (Rooms) is the landing view (Shell picks it). Extend a
    section by giving it a `render`; extend the tree by adding children.
    """
    return [
        NavItem('rooms', 'Rooms', 'meeting_room', render=render_rooms),
        NavItem('templates', 'Templates', 'wallpaper', render=render_templates),
        NavItem('displays', 'Displays', 'tv', render=render_displays),
        NavItem('settings', 'Preferences', 'settings', children=(
            NavItem('schedule', 'Schedule', 'schedule', render=render_schedule),
            NavItem('booking', 'Booking systems', 'event', render=render_booking_systems),
            NavItem('organizer', 'Organizer names', 'badge', render=render_organizer_names),
            NavItem('project', 'Project settings', 'place', render=render_project_settings),
            NavItem('global', 'Global settings', 'tune', render=render_global_settings),
        )),
    ]


def _root_path(project_name: str) -> str:
    """The extension page's own base URL, everything else routes relative
    to. Deferred `app.*` import: it exists only inside the nice4iot process;
    standalone passes its own fixed route in (see ui/standalone.py)."""
    from app.routes import project_extension_url
    return project_extension_url(project_name, 'epaper')


def _extra_routes(shell: Shell) -> dict[str, Callable[..., Any]]:
    """Room-detail deep link: /rooms/{room_id} opens straight to that room --
    see room/simplified_ui.py::render_rooms's room_id parameter."""
    return {'/rooms/{room_id}': lambda room_id: render_rooms(shell, room_id=room_id)}


def render(project_name: str, paths: Optional[EpaperPaths] = None,
          image_base_url: Optional[str] = None, root_path: Optional[str] = None) -> None:
    """Entry point. As a nice4iot extension it is called with just the
    project name (register_project_page) and derives the paths and
    root_path; standalone passes its fixed paths and route in (see
    ui/standalone.py).

    image_base_url is the display API's screen-image prefix (Templates'
    previews). nice4iot's register_project_page calls render(project_name)
    with nothing else, so it defaults to the same extension image route
    __init__.py's device card uses; standalone passes its own."""
    if image_base_url is None:
        image_base_url = f'/api/ext/epaper/{project_name}/screens'
    if root_path is None:
        root_path = _root_path(project_name)
    build_page(project_name, paths or _paths_for_project(project_name), _nav(),
              image_base_url, root_path, extra_routes=_extra_routes)
