from niceview import EditGridWrapper, ModelGrid

from extensions.epaper.paths import EpaperPaths
from extensions.epaper.room.backend import rooms_adapter
from extensions.epaper.room.models import RoomModel


def rooms_wrapper(paths: EpaperPaths, project_name: str) -> EditGridWrapper:
    """List<->editor drill-down for rooms, rendered as a nice4iot project tab
    and reused by standalone -- mirrors screens_wrapper()/schedules_wrapper().
    project_name is needed for the Displays tab (the displays grid joins
    nice4iot devices of that project)."""
    adapter = rooms_adapter(paths)
    # return DrillDownWrapper(
    #     RoomModel, adapter,  # list title/description come from RoomModel.Meta
    #     item_title_field='room_name',
    #     item_subtitle_fields=['room_number', 'room_type', 'capacity'],
    #     render_detail=lambda a, key, set_key: _render_detail(paths, project_name, a, key),
    # )
    from extensions.epaper.bookingsystem.models import BookingSystemModel
    from extensions.epaper.bookingsystem.backend import booking_systems_adapter, list_booking_systems
    grid = ModelGrid(RoomModel, adapter, auto_size_columns=True,
                     include=['room_number', 'room_name', 'room_type', 'capacity', 'notes', 'booking_system_id'])
    wrapper = EditGridWrapper(grid, search=True)
    # niceview's modelselect resolves an empty repository to options={}, which its own
    # select widget then treats as "no options defined" and raises -- so only register the
    # repository once there is at least one booking system to select (crashed the Add/Edit
    # dialog otherwise). With none registered, the field falls back to a disabled placeholder.
    if list_booking_systems(paths):
        wrapper = wrapper.with_repositories({BookingSystemModel: booking_systems_adapter(paths)})
    return wrapper

