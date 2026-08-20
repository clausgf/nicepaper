"""
Settings > Booking systems: a niceview DrillDownWrapper over the booking
directory (BookingSystemsAdapter), so the list, Add and Delete are niceview's;
this module only supplies the row and the detail (the BookingSystemModel form,
autosaving through the adapter).

A booking system is the connection/type; a room references one by id and adds
its own resource (iCal URL) in the room settings (see models/room.py).
"""
from niceview import DrillDownWrapper

from extensions.epaper.core.bookingsystem import BookingSystemsAdapter
from extensions.epaper.models.bookingsystem import BookingSystemModel

from .layout import Shell


def render_booking_systems(shell: Shell) -> None:
    adapter = BookingSystemsAdapter(shell.paths)
    DrillDownWrapper(
        BookingSystemModel, adapter,
        list_title='Booking systems',
        item_title_field='name',
        item_subtitle_fields=['type', 'update_interval'],
    ).render()
