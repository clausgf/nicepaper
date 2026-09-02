"""
Storage for rooms: one JSON file per room in EpaperPaths.room_dir, named by
the room's stable surrogate id (RoomModel.id), which is also what device
bindings reference. The id never changes, so a room can be renamed freely
by editing room_name/room_number.

Thin helpers over niceview's JsonAdapter (the same per-file adapter the
screen editor uses); the room form autosaves through its own JsonAdapter,
these cover the collection: list, read, create, delete. The UI collection
adapter is niceview's JsonDirectoryAdapter (rooms_adapter()) -- a directory of
one JSON per room keyed by RoomModel.id -- so the rooms UI is a plain
DrillDownWrapper + ModelForm with no hand-built list/detail chrome.
"""
from typing import Optional

from niceview import JsonAdapter, JsonDirectoryAdapter

from extensions.epaper.bookingsystem.backend import read_booking_system
from extensions.epaper.core.datasources.ical import get_from_ical
from extensions.epaper.room.models import RoomModel
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.util import logger


def room_path(paths: EpaperPaths, room_id: str):
    return paths.room_dir / f'{room_id}.json'


def room_adapter(paths: EpaperPaths, room_id: str) -> JsonAdapter:
    """JsonAdapter the room form autosaves through. create_if_not_exist is
    off so merely opening a missing id can't write a junk file whose
    generated id would not match its name (see RoomModel.id)."""
    return JsonAdapter(RoomModel, room_path(paths, room_id), create_if_not_exist=False)


def list_rooms(paths: EpaperPaths) -> list[RoomModel]:
    """Every room, sorted by name then number for a stable, human list order."""
    rooms = []
    for p in sorted(paths.room_dir.glob('*.json')):
        try:
            rooms.append(JsonAdapter(RoomModel, p, create_if_not_exist=False).read())
        except Exception as e:  # skip an unreadable file rather than break the list
            logger.warning(f"Skipping unreadable room {p}: {e}")
    return sorted(rooms, key=lambda r: (r.room_name.lower(), r.room_number))


def count_unreadable_rooms(paths: EpaperPaths) -> int:
    """How many files in room_dir the *actual* Rooms list (rooms_adapter(),
    a niceview JsonDirectoryAdapter -- used directly by both UIs' Rooms
    views) silently drops -- logged only, otherwise no trace anywhere.

    Deliberately not "try reading each file, count the exceptions": a
    single-file JsonAdapter.read() (as list_rooms() above uses) is lenient
    by default and recovers a malformed file into a *default* RoomModel
    instead of raising, so that approach never actually catches the common
    case (corrupted JSON) -- only diffing against what the adapter that
    backs the real list actually returns is guaranteed to match what's
    visible (or not) there."""
    on_disk = sum(1 for p in paths.room_dir.glob('*.json')
                  if p.is_file() and not p.name.startswith('.'))
    listed = sum(1 for _ in rooms_adapter(paths))
    return max(0, on_disk - listed)


def read_room(paths: EpaperPaths, room_id: str) -> Optional[RoomModel]:
    """The room with this id, or None if there is no such file."""
    if not room_path(paths, room_id).exists():
        return None
    return room_adapter(paths, room_id).read()


def create_room(paths: EpaperPaths) -> RoomModel:
    """Create a new room with a fresh id and default fields, and return it.
    The file is named by the generated id, so it matches RoomModel.id."""
    # id has a default_factory (uuid4().hex), but it sits in Annotated[...,
    # Field(...), niceview.Field(...)], a combination the pydantic mypy plugin
    # doesn't recognize as making the field optional.
    room = RoomModel()  # type: ignore[call-arg]
    room_adapter(paths, room.id).save(room)
    return room


def delete_room(paths: EpaperPaths, room_id: str) -> None:
    """Remove a room's file. Device bindings that still reference it are left
    dangling on purpose (flagged in the device card), not silently rewritten."""
    room_path(paths, room_id).unlink(missing_ok=True)


async def get_room_events(paths: EpaperPaths, room: RoomModel, force: bool = False) -> list:
    """This room's calendar events (sorted, from its booking system's iCal
    feed -- see BookingSystemModel and RoomModel.booking_system_id/
    booking_ical_url), for the simplified UI's Occupancy panel and
    RoomCalendarWidget.

    booking_ical_url, if set, is the room's own full feed URL (e.g. one iCal
    URL per resource on the same server); empty falls back to the booking
    system's own url (fine for a single-room setup). Credentials/headers/
    timing all come from the booking system -- get_from_ical() itself reads
    no config. Raises ValueError (not e.g. returning []) when the room isn't
    configured yet, so the panel can show why rather than an empty list
    indistinguishable from "no events".

    `force` bypasses the iCal cache's freshness/backoff checks -- for an
    explicit reload (room/simplified_ui.py's Occupancy panel, a booking
    system's "reload all rooms" action), not a widget's own render.

    get_from_ical() itself never raises (graceful degradation: it returns
    the last-known events, backing off from a failing feed instead of
    hammering it every render) -- this adapts that IcalStatus back to the
    raise-on-total-failure contract every caller here already expects: a
    RuntimeError only when there is no last-known data at all, same as
    before get_from_ical() gained backoff/status tracking."""
    if not room.booking_system_id:
        raise ValueError("This room has no booking system configured yet.")
    system = read_booking_system(paths, room.booking_system_id)
    if system is None:
        raise ValueError(f"Booking system '{room.booking_system_id}' not found.")
    url = room.booking_ical_url or system.url
    if not url:
        raise ValueError(f"Booking system '{system.name}' has no URL configured.")

    status = await get_from_ical(
        paths.ical_dir, paths.organizer_names_file, f"room-{room.id}", url,
        update_interval_s=int(system.update_interval.total_seconds()),
        max_days=system.max_days_ahead.days,
        username=system.username, password=system.password, headers=system.header or None,
        extract_organizer_from_summary=True, force=force)
    if status.events is None:
        raise RuntimeError(status.error or "Could not fetch calendar events.")
    return status.events


def rooms_adapter(paths: EpaperPaths) -> JsonDirectoryAdapter[RoomModel]:
    """The rooms collection as a niceview JsonDirectoryAdapter: a directory of
    one JSON per room, keyed by RoomModel.id (its default is a fresh uuid, so
    DrillDownWrapper's default Add -- create(RoomModel()) -- yields a new id and
    file). Gives the UI list/read/create/update/delete with no bespoke chrome;
    sorted by name then number for a stable, human list order."""
    return JsonDirectoryAdapter(
        RoomModel, paths.room_dir,
        sort_key=lambda r: (r.room_name.lower(), r.room_number),
    )
