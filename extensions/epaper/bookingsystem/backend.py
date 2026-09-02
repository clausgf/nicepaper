"""
Storage for booking systems: one JSON file per system in
EpaperPaths.booking_dir, named by the system's stable surrogate id
(BookingSystemModel.id), which is what RoomModel.booking_system_id references.

Same shape as room/backend.py: thin helpers over niceview's JsonAdapter plus a
booking_systems_adapter() -- niceview's JsonDirectoryAdapter over booking_dir,
keyed by BookingSystemModel.id -- so the UI is a plain DrillDownWrapper + ModelForm.
"""
from typing import Optional

from niceview import JsonAdapter, JsonDirectoryAdapter

from extensions.epaper.bookingsystem.models import BookingSystemModel
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


def count_unreadable_booking_systems(paths: EpaperPaths) -> int:
    """How many files in booking_dir the *actual* Booking systems list
    (booking_systems_adapter(), a niceview JsonDirectoryAdapter -- used
    directly by both UIs) silently drops. See room.backend.
    count_unreadable_rooms()'s docstring for why this diffs against the
    real adapter's own count rather than re-reading each file with a
    single-file JsonAdapter (lenient by default, so it wouldn't actually
    catch the common corrupted-JSON case)."""
    on_disk = sum(1 for p in paths.booking_dir.glob('*.json')
                  if p.is_file() and not p.name.startswith('.'))
    listed = sum(1 for _ in booking_systems_adapter(paths))
    return max(0, on_disk - listed)


def read_booking_system(paths: EpaperPaths, system_id: str) -> Optional[BookingSystemModel]:
    """The booking system with this id, or None if there is no such file."""
    if not booking_system_path(paths, system_id).exists():
        return None
    return booking_system_adapter(paths, system_id).read()


def create_booking_system(paths: EpaperPaths) -> BookingSystemModel:
    """Create a new booking system with a fresh id and default fields."""
    # id has a default_factory (uuid4().hex), but it sits in Annotated[...,
    # Field(...), niceview.Field(...)], a combination the pydantic mypy plugin
    # doesn't recognize as making the field optional.
    system = BookingSystemModel()  # type: ignore[call-arg]
    booking_system_adapter(paths, system.id).save(system)
    return system


def delete_booking_system(paths: EpaperPaths, system_id: str) -> None:
    """Remove a system's file. Rooms that still reference it are left dangling
    on purpose (the room's Booking system select keeps a dangling id visible),
    not silently rewritten."""
    booking_system_path(paths, system_id).unlink(missing_ok=True)


def booking_systems_adapter(paths: EpaperPaths) -> JsonDirectoryAdapter[BookingSystemModel]:
    """The booking-systems collection as a niceview JsonDirectoryAdapter: a
    directory of one JSON per system, keyed by BookingSystemModel.id (a fresh
    uuid by default, so DrillDownWrapper's default Add yields a new id and file).
    Gives the UI list/read/create/update/delete; sorted by name."""
    return JsonDirectoryAdapter(
        BookingSystemModel, paths.booking_dir,
        sort_key=lambda s: s.name.lower(),
    )
