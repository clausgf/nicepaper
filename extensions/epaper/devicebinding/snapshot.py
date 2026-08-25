"""
Per-device "last delivered" snapshot: the PNG a device's own alias URL last
served with a real 200 OK (not a 304 Not Modified), plus when -- so Display
Detail can show what a device is actually displaying right now, distinct
from what the current screen would render (core/imagecache.py's own cache
is keyed by screen/room only, with no device dimension, and is overwritten
independently of whether any device ever fetched it).

Written by api/endpoints.py's _render_screen_image() on every real 200 that
came in through a device's own alias URL; read by the simplified UI's
Display Detail (display/preview.py).

Synchronous, like devicebinding/backend.py: a handful of small files, no
aiofiles. Callers on the (async) image-serving path use asyncio.to_thread.
"""
import datetime
import shutil
from pathlib import Path
from typing import Optional

from extensions.epaper.devicebinding.models import DeviceSnapshot
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.util import logger


def device_snapshot_png_path(paths: EpaperPaths, device_name: str) -> Path:
    return paths.device_snapshot_dir / f'{device_name}.png'


def _meta_path(paths: EpaperPaths, device_name: str) -> Path:
    return paths.device_snapshot_dir / f'{device_name}.json'


def save_device_snapshot(paths: EpaperPaths, device_name: str, image_path: Path) -> None:
    """Copy image_path (the PNG about to be served to this device) into its
    snapshot slot, overwriting any previous one, and record the fetch time."""
    paths.device_snapshot_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(image_path, device_snapshot_png_path(paths, device_name))
    _meta_path(paths, device_name).write_text(
        DeviceSnapshot(fetched_at=datetime.datetime.now(datetime.timezone.utc)).model_dump_json())


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
