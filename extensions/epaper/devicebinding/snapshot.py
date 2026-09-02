"""
Per-device polling state: the PNG a device's own alias URL last served with
a real 200 OK (not a 304 Not Modified) plus when (fetched_at), and when the
device is next expected to poll again per the most recent Cache-Control:
max-age it was sent (next_expected_at) -- so Display Detail can show both
what a device is actually displaying right now (distinct from what the
current screen would render -- core/imagecache.py's own cache is keyed by
screen/room only, with no device dimension, and is overwritten independently
of whether any device ever fetched it) and whether it is overdue to check in
again.

fetched_at + the PNG are written by api/endpoints.py's _render_screen_image()
on every real 200 that came in through a device's own alias URL.
next_expected_at is written on *every* such poll, 200 or 304 alike, since a
304 still carries a fresh Cache-Control the device is expected to honor.
Both read by the simplified UI's Display Detail (display/preview.py) and
Displays list (display/backend.py's display_rows()).

Synchronous, like devicebinding/backend.py: a handful of small files, no
aiofiles. Callers on the (async) image-serving path use asyncio.to_thread.
"""
import datetime
import shutil
from pathlib import Path
from typing import Any, Optional

from extensions.epaper.devicebinding.models import DeviceSnapshot
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.util import logger


def device_snapshot_png_path(paths: EpaperPaths, device_name: str) -> Path:
    return paths.device_snapshot_dir / f'{device_name}.png'


def _meta_path(paths: EpaperPaths, device_name: str) -> Path:
    return paths.device_snapshot_dir / f'{device_name}.json'


def _write_snapshot(paths: EpaperPaths, device_name: str, **updates: Any) -> None:
    """Merge `updates` into this device's existing snapshot metadata (or a
    blank one) and write it back, so save_device_snapshot() and
    save_next_expected() never clobber a field only the other one sets."""
    paths.device_snapshot_dir.mkdir(parents=True, exist_ok=True)
    meta_path = _meta_path(paths, device_name)
    existing = None
    if meta_path.is_file():
        try:
            existing = DeviceSnapshot.model_validate_json(meta_path.read_text())
        except (OSError, ValueError):
            existing = None
    base = existing or DeviceSnapshot()
    meta_path.write_text(base.model_copy(update=updates).model_dump_json())


def save_device_snapshot(paths: EpaperPaths, device_name: str, image_path: Path) -> None:
    """Copy image_path (the PNG about to be served to this device) into its
    snapshot slot, overwriting any previous one, and record the fetch time."""
    shutil.copyfile(image_path, device_snapshot_png_path(paths, device_name))
    _write_snapshot(paths, device_name, fetched_at=datetime.datetime.now(datetime.timezone.utc))


def save_next_expected(paths: EpaperPaths, device_name: str,
                       next_expected_at: datetime.datetime) -> None:
    """Record when this device is next expected to poll again. Never touches
    the PNG or fetched_at -- see _write_snapshot()."""
    _write_snapshot(paths, device_name, next_expected_at=next_expected_at)


def read_device_snapshot(paths: EpaperPaths, device_name: str) -> Optional[DeviceSnapshot]:
    """This device's last-delivered snapshot metadata, or None if it has
    never fetched a real 200 yet (or the PNG is missing despite the sidecar
    -- treated the same as "no snapshot" rather than raised, matching this
    package's tolerance for a dangling/partial file, see backend.py)."""
    meta_path = _meta_path(paths, device_name)
    if not meta_path.is_file() or not device_snapshot_png_path(paths, device_name).is_file():
        return None
    try:
        return DeviceSnapshot.model_validate_json(meta_path.read_text())
    except (OSError, ValueError) as e:
        logger.warning(f"Invalid device snapshot metadata for {device_name!r}: {e}")
        return None
