"""
Load/save and lookups for the device bindings: the typed collection file
`device_bindings.json` (`dict[device_name, DeviceBinding]`) that maps a
nice4iot device name to the room it hangs in and the screen it renders.

Replaces the old `aliases.json` (device -> screen id). `get_device_bindings`
migrates that file on first read, so an existing installation keeps its
screen assignments without any manual step.

Synchronous: the store holds a handful of devices in a tiny file, so it is
read/written directly (like the editor's JsonAdapter, screen/ui.py),
not through aiofiles -- the one caller on the image-serving path
(screen.backend.resolve_screen_id) only does a small, infrequent read. There is
no cache; add a per-root cache dict if a profile ever shows it is needed.
"""
import json
from pathlib import Path
from typing import Optional

from pydantic import TypeAdapter, ValidationError

from extensions.epaper.devicebinding.models import DeviceBinding
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.util import logger

# Legacy bare alias file (device name -> screen id) migrated on first read.
_LEGACY_ALIAS_FILENAME = "aliases.json"

_BINDINGS = TypeAdapter(dict[str, DeviceBinding])

# Sentinel so set_device_binding() can tell "leave this field unchanged"
# apart from "set it to None" (clear it) -- a plain None means clear.
_UNSET = object()


def _read_json(path: Path) -> Optional[object]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        logger.warning(f"Error reading {path}: {e}")
        return None


def _migrate_legacy_aliases(paths: EpaperPaths) -> dict[str, DeviceBinding]:
    """Convert a legacy aliases.json ({name: screen_id}) into device
    bindings and write device_bindings.json. Returns the migrated bindings,
    or {} if there is nothing to migrate."""
    legacy = _read_json(paths.root / _LEGACY_ALIAS_FILENAME)
    if not isinstance(legacy, dict):
        return {}
    bindings = {name: DeviceBinding(screen_id=screen_id)
                for name, screen_id in legacy.items() if isinstance(name, str)}
    _write_device_bindings(paths, bindings)
    logger.info(f"Migrated {len(bindings)} alias(es) to {paths.device_bindings_file}")
    return bindings


def get_device_bindings(paths: EpaperPaths) -> dict[str, DeviceBinding]:
    """All device bindings (device name -> DeviceBinding), or {} if none.

    Migrates a legacy aliases.json on first read (only when
    device_bindings.json does not exist yet), so this stays the single entry
    point every reader goes through."""
    if not paths.device_bindings_file.exists():
        return _migrate_legacy_aliases(paths)
    raw = _read_json(paths.device_bindings_file)
    if raw is None:
        return {}
    try:
        return _BINDINGS.validate_python(raw)
    except ValidationError as e:
        logger.warning(f"Invalid device bindings in {paths.device_bindings_file}: {e}")
        return {}


def _write_device_bindings(paths: EpaperPaths, bindings: dict[str, DeviceBinding]) -> None:
    # atomic .tmp -> rename, matching JsonAdapter's writes
    text = json.dumps(_BINDINGS.dump_python(bindings, mode='json'), indent=2)
    tmp = paths.device_bindings_file.with_name(paths.device_bindings_file.name + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.rename(paths.device_bindings_file)


def get_device_binding(paths: EpaperPaths, device_name: str) -> DeviceBinding:
    """This device's binding, or an empty one when it has none yet."""
    return get_device_bindings(paths).get(device_name, DeviceBinding())


def set_device_binding(paths: EpaperPaths, device_name: str, *,
                       room_id: object = _UNSET, screen_id: object = _UNSET) -> None:
    """Update one device's binding. Each of room_id/screen_id is left
    unchanged when not passed, and cleared when passed None. The entry is
    dropped once both are empty, so an unassigned device leaves no row
    behind (the empty-file equivalent of removing an alias)."""
    bindings = get_device_bindings(paths)
    binding = bindings.get(device_name, DeviceBinding())
    if room_id is not _UNSET:
        binding.room_id = room_id  # type: ignore[assignment]
    if screen_id is not _UNSET:
        binding.screen_id = screen_id  # type: ignore[assignment]
    if binding.room_id is None and binding.screen_id is None:
        bindings.pop(device_name, None)
    else:
        bindings[device_name] = binding
    _write_device_bindings(paths, bindings)


def resolve_screen_id(paths: EpaperPaths, device_name: str) -> str:
    """Resolve a display id to its target screen id: a device addressed by
    its own name resolves to the screen bound to it, so a display only ever
    needs to know its name. Falls back to the given id unchanged when there
    is no binding (or the binding has no screen), so a real screen id passes
    straight through. Renamed from the former _resolve_alias()."""
    binding = get_device_bindings(paths).get(device_name)
    return binding.screen_id if binding and binding.screen_id else device_name


def devices_in_room(paths: EpaperPaths, room_id: str) -> list[str]:
    """Names of the devices assigned to a room (reverse of DeviceBinding.
    room_id), sorted. The room stores no device ids itself; this scans the
    bindings instead."""
    return sorted(name for name, b in get_device_bindings(paths).items()
                  if b.room_id == room_id)
