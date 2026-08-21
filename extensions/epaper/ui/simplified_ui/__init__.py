"""
Simplified UI: a room-focused, e-paper-only alternative to the standalone/
nice4iot editors, rendered as the extension's standalone project page
(register_project_page in extensions/epaper/__init__.py).

`render(project_name)` is the entry point nice4iot calls. It defines the
sidebar navigation and hands off to layout.build_page(); every section's
content lives in its own module (rooms, displays, booking).
"""
from typing import Optional

from extensions.epaper.paths import EpaperPaths

from extensions.epaper.bookingsystem.simplified_ui import render_booking_systems
from extensions.epaper.room.simplified_ui import render_rooms

from .displays import render_displays
from .layout import NavItem, build_page


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
    """Two-level sidebar: two leaf sections plus a Settings group.

    The first leaf (Rooms) is the landing view (Shell picks it). Extend a
    section by giving it a `render`; extend the tree by adding children.
    """
    return [
        NavItem('rooms', 'Rooms', 'meeting_room', render=render_rooms),
        NavItem('displays', 'Displays', 'tv', render=render_displays),
        NavItem('settings', 'Preferences', 'settings', children=(
            NavItem('booking', 'Booking systems', 'event', render=render_booking_systems),
        )),
    ]


def render(project_name: str, paths: Optional[EpaperPaths] = None) -> None:
    """Entry point. As a nice4iot extension it is called with just the
    project name (register_project_page) and derives the paths; standalone
    passes its fixed paths in (see ui/standalone.py)."""
    build_page(project_name, paths or _paths_for_project(project_name), _nav())
