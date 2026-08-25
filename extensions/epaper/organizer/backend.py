"""
Storage for organizer_names_file (paths.py): a flat JSON array of names,
read by core/datasources/ical.py as a fallback to extract an organizer from
an event summary when the feed has no ORGANIZER field. Previously admin-only
(hand-placed on disk, see examples/organizer_names.json); these two functions
give the simplified UI (organizer/simplified_ui.py) a place to read/write it.
"""
import json
from typing import List

from extensions.epaper.paths import EpaperPaths
from extensions.epaper.util import logger


def read_organizer_names(paths: EpaperPaths) -> List[str]:
    path = paths.organizer_names_file
    if not path.is_file():
        return []
    try:
        names = json.loads(path.read_text())
    except Exception as e:
        logger.warning(f"Organizer names file {path} is invalid: {e}")
        return []
    return [str(n) for n in names] if isinstance(names, list) else []


def save_organizer_names(paths: EpaperPaths, names: List[str]) -> None:
    paths.organizer_names_file.write_text(json.dumps(names, indent=2, ensure_ascii=False))
