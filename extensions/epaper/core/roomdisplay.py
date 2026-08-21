"""
The displays grid's data: it joins nice4iot devices (name, last-seen ->
online) with our device bindings (room_id, screen_id) and the bound room
(building/floor/number) into RoomDisplayRow rows.

nice4iot owns devices; we only reference them by name. `_project_devices`
reaches into nice4iot's device backend (in-process; there is no sanctioned
extension getter yet -- see docs/nice4iot-extension-wishlist.md) and returns
[] outside nice4iot (standalone/tests), so the grid degrades to empty rather
than breaking. Tests monkeypatch `_project_devices`.

RoomDisplaysAdapter is a niceview CollectionAdapter so the UI is a plain
EditGridWrapper: inline edits to screen_id persist via update() ->
set_device_binding; delete() unassigns the device from its room (it does not
delete the nice4iot device).
"""
import datetime
from typing import Iterator, Optional

from extensions.epaper.core.devicebinding import get_device_bindings, set_device_binding
from extensions.epaper.room.backend import read_room
from extensions.epaper.models.roomdisplay import RoomDisplayRow
from extensions.epaper.paths import EpaperPaths

# A device counts as online if it was seen within this window (its last_seen_at
# is refreshed on every authenticated request/telemetry push).
ONLINE_THRESHOLD = datetime.timedelta(minutes=5)


def _project_devices(project_name: str) -> list:
    """nice4iot devices of a project (objects with .name and .last_seen_at), or
    [] outside nice4iot. Deferred import: app.* exists only in that process."""
    try:
        from app.core.device.backend import get_devices
    except ImportError:
        return []
    try:
        return get_devices(project_name)
    except Exception:
        return []


def _device_url(project_name: str, device_name: str) -> str:
    try:
        from app.routes import device_url
    except ImportError:
        return ''
    return device_url(project_name, device_name)


def _is_online(device) -> bool:
    last_seen = getattr(device, 'last_seen_at', None)
    if last_seen is None:
        return False
    return datetime.datetime.now(datetime.timezone.utc) - last_seen < ONLINE_THRESHOLD


def display_rows(paths: EpaperPaths, project_name: str,
                 room_id: Optional[str] = None) -> list[RoomDisplayRow]:
    """One row per device, filtered to `room_id` when given (the room tab) or
    all devices otherwise (a global list). building/floor/number come from the
    device's *own* bound room, so the columns are meaningful either way."""
    bindings = get_device_bindings(paths)
    rows: list[RoomDisplayRow] = []
    for device in _project_devices(project_name):
        binding = bindings.get(device.name)
        bound_room_id = binding.room_id if binding else None
        if room_id is not None and bound_room_id != room_id:
            continue
        room = read_room(paths, bound_room_id) if bound_room_id else None
        rows.append(RoomDisplayRow(
            device_name=device.name,
            screen_id=(binding.screen_id if binding else None) or '',
            building=(room.building if room else None) or '',
            floor=(room.floor if room else None) or '',
            room_number=(room.room_number if room else None) or '',
            online=_is_online(device),
            rssi=None, battery_voltage=None, alarm_count=None,  # no source yet
            device_url=_device_url(project_name, device.name),
        ))
    return sorted(rows, key=lambda r: r.device_name)


def assignable_devices(paths: EpaperPaths, project_name: str, room_id: str) -> list[str]:
    """Device names that can be added to this room: every project device not
    already in it (assigning one that is in another room moves it here)."""
    bindings = get_device_bindings(paths)
    return sorted(d.name for d in _project_devices(project_name)
                  if (bindings.get(d.name).room_id if bindings.get(d.name) else None) != room_id)


class RoomDisplaysAdapter:
    """niceview CollectionAdapter[RoomDisplayRow], keyed by device name. Only
    screen_id is writable (into the device binding); delete unassigns the
    device from its room. Duck-typed like the other adapters here."""

    def __init__(self, paths: EpaperPaths, project_name: str, room_id: Optional[str] = None) -> None:
        self._paths = paths
        self._project_name = project_name
        self._room_id = room_id

    def _rows(self) -> list[RoomDisplayRow]:
        return display_rows(self._paths, self._project_name, self._room_id)

    def __iter__(self) -> Iterator[RoomDisplayRow]:
        return iter(self._rows())

    def key_from_item(self, item: RoomDisplayRow) -> str:
        return item.device_name

    def read(self, key: str) -> RoomDisplayRow:
        for row in self._rows():
            if row.device_name == key:
                return row
        raise KeyError(key)

    def update(self, item: RoomDisplayRow) -> RoomDisplayRow:
        # only screen_id is editable; '' clears the assignment
        set_device_binding(self._paths, item.device_name, screen_id=item.screen_id or None)
        return item

    def delete(self, key: str) -> None:
        # remove the display from its room (keeps the nice4iot device + its screen)
        set_device_binding(self._paths, key, room_id=None)

    def create(self, item: RoomDisplayRow) -> RoomDisplayRow:
        set_device_binding(self._paths, item.device_name, room_id=self._room_id,
                           screen_id=item.screen_id or None)
        return item

    def items(self) -> Iterator[tuple[str, RoomDisplayRow]]:
        for row in self._rows():
            yield row.device_name, row
