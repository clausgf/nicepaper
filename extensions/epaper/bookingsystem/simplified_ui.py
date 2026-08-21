"""
Settings > Booking systems: a niceview DrillDownWrapper over the booking
directory (booking_systems_adapter, a JsonDirectoryAdapter), so the list, Add
and Delete are niceview's; this module only supplies the row and the detail (the
BookingSystemModel form, autosaving through the adapter).

A booking system is the connection/type; a room references one by id and adds
its own resource (iCal URL) in the room settings (see room/models.py).
"""
from niceview import DrillDownWrapper

from extensions.epaper.bookingsystem.backend import booking_systems_adapter
from extensions.epaper.bookingsystem.models import BookingSystemModel

from extensions.epaper.ui.simplified_ui.layout import Shell


def render_booking_systems(shell: Shell) -> None:
    adapter = booking_systems_adapter(shell.paths)
    DrillDownWrapper(
        BookingSystemModel, adapter,  # list title/description come from BookingSystemModel.Meta
        item_title_field='name',
        item_subtitle_fields=['type', 'update_interval'],
    ).render()
