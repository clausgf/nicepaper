"""
Storage for booking systems: one JSON file per system in
EpaperPaths.booking_dir, named by the system's stable surrogate id
(BookingSystemModel.id), which is what RoomModel.booking_system_id references.

Same shape as core/room.py: thin helpers over niceview's JsonAdapter plus a
BookingSystemsAdapter (CollectionAdapter) so the UI is a plain
DrillDownWrapper + ModelForm.
"""
from typing import Iterator, Optional

from niceview import JsonAdapter

from extensions.epaper.models.bookingsystem import BookingSystemModel
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.util import logger


def booking_system_path(paths: EpaperPaths, system_id: str):
    return paths.booking_dir / f'{system_id}.json'


def booking_system_adapter(paths: EpaperPaths, system_id: str) -> JsonAdapter:
    """JsonAdapter the form autosaves through. create_if_not_exist is off so
    opening a missing id can't write a junk file whose generated id would not
    match its name (see BookingSystemModel.id)."""
    return JsonAdapter(BookingSystemModel, booking_system_path(paths, system_id), create_if_not_exist=False)


def list_booking_systems(paths: EpaperPaths) -> list[BookingSystemModel]:
    """Every booking system, sorted by name for a stable, human list order."""
    systems = []
    for p in sorted(paths.booking_dir.glob('*.json')):
        try:
            systems.append(JsonAdapter(BookingSystemModel, p, create_if_not_exist=False).read())
        except Exception as e:  # skip an unreadable file rather than break the list
            logger.warning(f"Skipping unreadable booking system {p}: {e}")
    return sorted(systems, key=lambda s: s.name.lower())


def read_booking_system(paths: EpaperPaths, system_id: str) -> Optional[BookingSystemModel]:
    """The booking system with this id, or None if there is no such file."""
    if not booking_system_path(paths, system_id).exists():
        return None
    return booking_system_adapter(paths, system_id).read()


def create_booking_system(paths: EpaperPaths) -> BookingSystemModel:
    """Create a new booking system with a fresh id and default fields."""
    system = BookingSystemModel()
    booking_system_adapter(paths, system.id).save(system)
    return system


def delete_booking_system(paths: EpaperPaths, system_id: str) -> None:
    """Remove a system's file. Rooms that still reference it are left dangling
    on purpose (the room's Booking system select keeps a dangling id visible),
    not silently rewritten."""
    booking_system_path(paths, system_id).unlink(missing_ok=True)


class BookingSystemsAdapter:
    """niceview CollectionAdapter[BookingSystemModel] over booking_dir, keyed by
    id. Duck-typed (CollectionAdapter is a Protocol), like core/room.RoomsAdapter."""

    def __init__(self, paths: EpaperPaths) -> None:
        self._paths = paths

    def __iter__(self) -> Iterator[BookingSystemModel]:
        return iter(list_booking_systems(self._paths))

    def key_from_item(self, item: BookingSystemModel) -> str:
        return item.id

    def read(self, key: str) -> BookingSystemModel:
        system = read_booking_system(self._paths, key)
        if system is None:
            raise KeyError(key)
        return system

    def create(self, item: BookingSystemModel) -> BookingSystemModel:
        booking_system_adapter(self._paths, item.id).save(item)
        return item

    def update(self, item: BookingSystemModel) -> BookingSystemModel:
        booking_system_adapter(self._paths, item.id).save(item)
        return item

    def delete(self, key: str) -> None:
        delete_booking_system(self._paths, key)

    def items(self) -> Iterator[tuple[str, BookingSystemModel]]:
        for system in list_booking_systems(self._paths):
            yield system.id, system
