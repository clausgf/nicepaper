"""
Preferences > Booking systems: the simplified UI's view onto
bookingsystem/ui.py::booking_systems_wrapper(), which also backs the nice4iot
project tab of the same name -- see that module for the list/detail/editor
implementation.

A booking system is the connection/type; a room references one by id and adds
its own resource (iCal URL) in the room settings (see room/models.py).
"""
from extensions.epaper.bookingsystem.backend import count_unreadable_booking_systems
from extensions.epaper.bookingsystem.ui import booking_systems_wrapper
from extensions.epaper.ui.cards import unreadable_items_banner
from extensions.epaper.ui.simplified_ui.layout import Shell


def render_booking_systems(shell: Shell) -> None:
    unreadable_items_banner(count_unreadable_booking_systems(shell.paths), 'booking system(s)')
    booking_systems_wrapper(shell.paths).render()
