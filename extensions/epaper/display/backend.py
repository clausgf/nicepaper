"""
Displays data: it joins nice4iot devices (name, last-seen -> online) with our
device bindings (room_id, screen_id) and the bound room (building/floor/
number/room_label) into RoomDisplayRow rows.

nice4iot owns devices; we only reference them by name. `_project_devices`
reaches into nice4iot's device backend (in-process; there is no sanctioned
extension getter yet -- see docs/nice4iot-extension-wishlist.md) and returns
[] outside nice4iot (standalone/tests), so any UI built on this degrades to
empty rather than breaking. Tests monkeypatch `_project_devices`. rssi/
battery_voltage come from `_device_runtime`'s DeviceRuntime (its last
system-telemetry push); alarm_count from the device's own `active_alarms`
property (a live alarm-backend query) -- both None/absent outside nice4iot,
same degrade-to-empty pattern. A non-finite reading (NaN/inf -- a bad sensor
sample) is treated the same as no reading at all: passing it through would
crash the simplified UI's bar-index arithmetic later (int() has no NaN/inf
representation).

RoomDisplaysAdapter is a niceview CollectionAdapter: edits to screen_id persist
via update() -> set_device_binding; delete() unassigns the device from its
room (it does not delete the nice4iot device); rename() reassigns a row to a
different device (see its own docstring).
"""
import datetime
import math
from typing import Iterator, Optional

from extensions.epaper.devicebinding.backend import get_device_bindings, set_device_binding
from extensions.epaper.room.backend import read_room
from extensions.epaper.display.models import RoomDisplayRow
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


def _device_runtime(project_name: str, device_name: str):
    """nice4iot's DeviceRuntime for this device (rssi/battery_voltage
    properties over its last system-telemetry push), or None outside
    nice4iot/on error -- same in-process reach-in as _project_devices."""
    try:
        from app.core.device.backend import read_runtime
    except ImportError:
        return None
    try:
        return read_runtime(project_name, device_name)
    except Exception:
        return None


def device_epaper_telemetry(project_name: str, device_name: str
                            ) -> tuple[dict, dict, Optional[datetime.datetime]]:
    """(metrics, labels, reported_at) from esp32paper's latest kind='epaper'
    telemetry push -- numerics (image_status, ...) and strings (panel,
    panels, ...), cached in nice4iot's runtime sidecar via
    register_telemetry_cache_kind('epaper') in extensions/epaper/__init__.py.
    ({}, {}, None) outside nice4iot/on error, or if the device never sent
    one -- same degrade-to-empty pattern as _device_runtime()."""
    runtime = _device_runtime(project_name, device_name)
    if runtime is None:
        return {}, {}, None
    metrics = getattr(runtime, 'kind_metrics', {}).get('epaper', {})
    labels = getattr(runtime, 'kind_labels', {}).get('epaper', {})
    reported_at = getattr(runtime, 'kind_reported_at', {}).get('epaper')
    return metrics, labels, reported_at


def device_epaper_labels(project_name: str, device_name: str) -> dict:
    """Just the 'panel'/'panels' labels half of device_epaper_telemetry(),
    for callers that don't need the numerics/timestamp too."""
    return device_epaper_telemetry(project_name, device_name)[1]


def panel_mismatch_hint(paths: EpaperPaths, panel_types: dict, panel_type_id: Optional[str],
                        reported_panel: str) -> Optional[str]:
    """Text warning when `reported_panel` (esp32paper's active-panel telemetry
    label) doesn't line up with panel_type_id's catalog entry (`panel_types`,
    catalog.backend.get_panel_types()'s return value), or None when there's
    nothing to flag (no report yet, or it matches). Shared by every place
    that shows a device's panel type: nice4iot's Settings/Dashboard cards
    (devicebinding/ui.py) and the simplified UI's Displays detail
    (display/simplified_ui.py, room/simplified_ui.py)."""
    from extensions.epaper.catalog.backend import get_panel_type

    if not reported_panel:
        return None
    selected_panel_type = get_panel_type(panel_type_id, paths)
    if selected_panel_type is not None:
        if selected_panel_type.panel_id == reported_panel:
            return None
        return (f'Firmware reports panel "{reported_panel}", which does not match the '
                f'selected panel type ("{selected_panel_type.panel_id or "—"}").')
    matches = sorted(pt.name for pt in panel_types.values() if pt.panel_id == reported_panel)
    hint = f' Matches: {", ".join(matches)}.' if matches else ' No catalog entry for it yet.'
    return f'Firmware reports panel "{reported_panel}".{hint}'


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
    from extensions.epaper.catalog.backend import get_panel_types, panel_type_label

    bindings = get_device_bindings(paths)
    panel_types = get_panel_types(paths)
    rows: list[RoomDisplayRow] = []
    for device in _project_devices(project_name):
        binding = bindings.get(device.name)
        bound_room_id = binding.room_id if binding else None
        if room_id is not None and bound_room_id != room_id:
            continue
        room = read_room(paths, bound_room_id) if bound_room_id else None
        runtime = _device_runtime(project_name, device.name)
        rssi = getattr(runtime, 'rssi', None)
        battery_voltage = getattr(runtime, 'battery_voltage', None)
        epaper_labels = getattr(runtime, 'kind_labels', {}).get('epaper', {})
        panel_type_id = binding.panel_type_id if binding else None
        reported_panel = epaper_labels.get('panel', '')
        panel_type = panel_types.get(panel_type_id) if panel_type_id else None
        # "—" (not '') so a missing panel type still joins cleanly into the
        # simplified UI's " · "-separated row subtitle (ModelList._item_subtitle
        # doesn't skip empty parts, which would otherwise show as a stray " · ")
        panel_label = panel_type_label(panel_type) if panel_type is not None else '—'
        if panel_mismatch_hint(paths, panel_types, panel_type_id, reported_panel):
            panel_label = f'{panel_label} ⚠'
        rows.append(RoomDisplayRow(
            device_name=device.name,
            screen_id=(binding.screen_id if binding else None) or '',
            panel_type_id=panel_type_id,
            reported_panel=reported_panel,
            panel_label=panel_label,
            reported_panels=epaper_labels.get('panels', ''),
            room_label=(room.room_label if room else None) or '',
            building=(room.building if room else None) or '',
            floor=(room.floor if room else None) or '',
            room_number=(room.room_number if room else None) or '',
            is_active=getattr(device, 'is_active', True),
            is_provisioning_approved=getattr(device, 'is_provisioning_approved', False),
            online=_is_online(device),
            last_seen_at=getattr(device, 'last_seen_at', None),
            firmware_version=getattr(device, 'firmware_version', '') or '',
            rssi=round(rssi) if rssi is not None and math.isfinite(rssi) else None,
            battery_voltage=battery_voltage if battery_voltage is not None and math.isfinite(battery_voltage) else None,
            alarm_count=getattr(device, 'active_alarms', None),
            device_url=_device_url(project_name, device.name),
        ))
    return sorted(rows, key=lambda r: r.device_name)


def assignable_devices(paths: EpaperPaths, project_name: str, room_id: str) -> list[str]:
    """Device names that can be added to this room: every project device not
    already in it (assigning one that is in another room moves it here)."""
    bindings = get_device_bindings(paths)
    return sorted(d.name for d in _project_devices(project_name)
                  if (b := bindings.get(d.name)) is None or b.room_id != room_id)


def project_device_names(project_name: str) -> list[str]:
    """Every nice4iot device name in the project, sorted, regardless of room
    assignment -- unlike assignable_devices(), for correcting which device an
    existing display row means rather than adding a new one. [] outside
    nice4iot (standalone/tests), same as _project_devices()."""
    return sorted(d.name for d in _project_devices(project_name))


def available_screen_ids(paths: EpaperPaths, device_name: str) -> list[str]:
    """Screen ids selectable for device_name's Screen field (the simplified
    UI's Displays tabs -- room/simplified_ui.py's _display_detail and this
    package's own render_displays()): every screen (real files plus the
    auto-generated Room Calendar templates, screen.backend.
    synthetic_roomcalendar_screens) when the device has no panel_type_id set
    (devicebinding/ui.py, the nice4iot device card); otherwise only the ones
    matching it (screen.backend.screens_matching_panel_type) -- plus the
    currently assigned screen even if it no longer matches, so a mismatch
    stays visible rather than silently dropped (same dangling-reference
    precedent as booking_system_id elsewhere)."""
    from extensions.epaper.catalog.backend import get_panel_type
    from extensions.epaper.screen.backend import screens_matching_panel_type, synthetic_roomcalendar_screens

    binding = get_device_bindings(paths).get(device_name)
    panel_type = get_panel_type(binding.panel_type_id, paths) if binding else None
    if panel_type is None:
        options = sorted({*(p.stem for p in paths.screen_dir.glob('*.json')),
                          *synthetic_roomcalendar_screens(paths)})
    else:
        options = sorted(screens_matching_panel_type(paths, panel_type))
    if binding and binding.screen_id and binding.screen_id not in options:
        options = sorted([*options, binding.screen_id])
    return options


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
        # screen_id/panel_type_id are the only editable fields; '' clears an
        # assignment (screen_id/panel_type_id both persisted here even though
        # the simplified UI currently writes panel_type_id through a plain
        # ui.select with its own on_change instead of this generic path -- see
        # display/simplified_ui.py, room/simplified_ui.py -- so a screen_id-only
        # ModelForm autosave doesn't accidentally clear an already-set panel type)
        set_device_binding(self._paths, item.device_name, screen_id=item.screen_id or None,
                           panel_type_id=item.panel_type_id or None)
        return item

    def delete(self, key: str) -> None:
        # remove the display from its room (keeps the nice4iot device + its screen)
        set_device_binding(self._paths, key, room_id=None)

    def rename(self, old_device_name: str, new_device_name: str) -> str:
        """Move this row's room/screen assignment to a different device --
        e.g. correcting which device was actually picked for it. Unbinds the
        room from the old device and binds it (with the same screen) to the
        new one; a device already in another room is moved here, same as
        assignable_devices()/create() already allow. Returns the new key."""
        if new_device_name == old_device_name:
            return old_device_name
        old = self.read(old_device_name)
        set_device_binding(self._paths, new_device_name, room_id=self._room_id,
                           screen_id=old.screen_id or None)
        set_device_binding(self._paths, old_device_name, room_id=None)
        return new_device_name

    def create(self, item: RoomDisplayRow) -> RoomDisplayRow:
        set_device_binding(self._paths, item.device_name, room_id=self._room_id,
                           screen_id=item.screen_id or None)
        return item

    def items(self) -> Iterator[tuple[str, RoomDisplayRow]]:
        for row in self._rows():
            yield row.device_name, row
