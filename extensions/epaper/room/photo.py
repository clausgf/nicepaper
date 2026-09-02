"""
Room photo storage: at most one image file per room, in
EpaperPaths.room_photo_dir, named `<room_id>.<ext>` -- deliberately not
asset_dir (the project directory the Image widget reads from), since a room
photo belongs to the extension, not the user's project files (see
room/simplified_ui.py, uploaded through the room detail's Settings tab and
shown there plus on Occupancy/Displays).

Synchronous, like room/backend.py: a handful of small files, no aiofiles.
"""
from pathlib import Path
from typing import Optional

from extensions.epaper.paths import EpaperPaths

ALLOWED_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def room_photo_path(paths: EpaperPaths, room_id: str) -> Optional[Path]:
    """The room's photo file, or None if it has none."""
    matches = sorted(paths.room_photo_dir.glob(f'{room_id}.*'))
    return matches[0] if matches else None


def save_room_photo(paths: EpaperPaths, room_id: str, filename: str, content: bytes) -> None:
    """Store an uploaded photo, replacing any previous one (even under a
    different extension). Rejects a non-image extension rather than trusting
    the browser-supplied content type."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported image type '{suffix or filename}'.")
    delete_room_photo(paths, room_id)
    paths.room_photo_dir.mkdir(parents=True, exist_ok=True)
    (paths.room_photo_dir / f'{room_id}{suffix}').write_bytes(content)


def delete_room_photo(paths: EpaperPaths, room_id: str) -> None:
    """Idempotent: removing a room with no photo does nothing."""
    for p in paths.room_photo_dir.glob(f'{room_id}.*'):
        p.unlink(missing_ok=True)
