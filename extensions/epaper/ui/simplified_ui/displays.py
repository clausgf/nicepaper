"""
Displays section: the flat, project-wide list of e-paper displays.

A display is a nice4iot device (see extensions/epaper/__init__.py,
register_device_card). This is the shared displays grid without a room filter,
so every device shows with its room (building/floor/number), online state and
screen. Assigning a display to a room happens in the room's Displays tab (or
the device's E-Paper card), so there is no Add here.
"""
from .displays_grid import render_displays_grid
from .layout import Shell


def render_displays(shell: Shell) -> None:
    render_displays_grid(shell, room_id=None)
