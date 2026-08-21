"""
The panel and palette catalogs.

Both ship as package resources (`resources/displays.json`,
`resources/color_models.json`) so they are versioned with the code and a
new nicepaper release actually reaches existing installations -- see
`models/display.py` for why neither belongs in GlobalConfig. Each can be
extended per data root by a file of the same name in `paths.root`
(`data/displays.json` standalone, `<project>/.epaper/displays.json` as a
nice4iot extension): entries are merged by id, the root file wins, so a
root file can both add hardware we don't ship and correct an entry we do.

Only the palettes matter at render time -- a screen stores the *values*
a display preset gave it, not a reference to the preset, so editing
`displays.json` never changes an existing screen's image. Editing
`color_models.json` does, hence `color_models_mtime()` for the render
cache (see screen/backend.py).
"""
import importlib.resources
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import TypeAdapter

from extensions.epaper.models.display import ColorModel, DisplayModel
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.util import logger

__all__ = [
    "get_color_models", "get_color_model", "get_displays", "get_display",
    "color_models_mtime",
]

_COLOR_MODELS_RESOURCE = "color_models.json"
_DISPLAYS_RESOURCE = "displays.json"

_color_models_adapter = TypeAdapter(List[ColorModel])
_displays_adapter = TypeAdapter(List[DisplayModel])

# parsed package resources, read once per process (they can't change
# without a redeploy)
_builtin_cache: Dict[str, list] = {}
# parsed root overlays, keyed by file path and invalidated by mtime, so
# an edited file is picked up without a restart -- the same source-of-
# truth-stays-on-disk approach the screen cache uses
_overlay_cache: Dict[str, Tuple[Optional[float], list]] = {}


def _builtin(resource: str, adapter: TypeAdapter) -> list:
    cached = _builtin_cache.get(resource)
    if cached is None:
        text = (importlib.resources.files(__package__) / "resources" / resource).read_text(encoding="utf-8")
        cached = adapter.validate_json(text)
        _builtin_cache[resource] = cached
    return cached


def _file_mtime(path: Path) -> Optional[float]:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _overlay(path: Path, adapter: TypeAdapter) -> list:
    """Entries from a root catalog file, or [] if it doesn't exist. A file
    that exists but can't be read/parsed is logged and treated as empty
    rather than raised: a typo in an optional extra catalog must not take
    the built-in one (and with it every screen) down with it."""
    mtime = _file_mtime(path)
    key = str(path)
    cached = _overlay_cache.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    items: list = []
    if mtime is not None:
        try:
            items = adapter.validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.warning(f"Error reading catalog file {path}: {e}")
    _overlay_cache[key] = (mtime, items)
    return items


def _merged(builtin: list, overlay: list) -> dict:
    """Built-in entries first, root entries second, keyed by id -- so a
    root entry with a built-in id replaces it and any other is added."""
    return {item.id: item for item in (*builtin, *overlay)}


def get_color_models(paths: Optional[EpaperPaths] = None) -> Dict[str, ColorModel]:
    """All known palettes by id. `paths` adds/overrides them from that
    root's color_models.json; omit it where no root is in scope."""
    builtin = _builtin(_COLOR_MODELS_RESOURCE, _color_models_adapter)
    overlay = _overlay(paths.color_model_file, _color_models_adapter) if paths else []
    return _merged(builtin, overlay)


def get_color_model(id: Optional[str], paths: Optional[EpaperPaths] = None) -> Optional[ColorModel]:
    """The palette with this id, or None for an empty/unknown id -- which
    callers treat as 'don't quantize', i.e. serve the RGB image."""
    if not id:
        return None
    color_model = get_color_models(paths).get(id)
    if color_model is None:
        logger.warning(f"Unknown color model {id!r}, serving the unquantized image instead")
    return color_model


def get_displays(paths: Optional[EpaperPaths] = None) -> Dict[str, DisplayModel]:
    """All known panel presets by id, root entries merged in as above."""
    builtin = _builtin(_DISPLAYS_RESOURCE, _displays_adapter)
    overlay = _overlay(paths.display_file, _displays_adapter) if paths else []
    return _merged(builtin, overlay)


def get_display(id: Optional[str], paths: Optional[EpaperPaths] = None) -> Optional[DisplayModel]:
    """The panel preset with this id, or None if it is empty/unknown. An
    unknown id is not an error: presets are only a template, and a screen
    that references one that has since been removed still renders from
    its own fields."""
    if not id:
        return None
    return get_displays(paths).get(id)


def color_models_mtime(paths: EpaperPaths) -> Optional[float]:
    """mtime of this root's color_models.json, or None if it has none.
    Part of the screen cache key (screen/backend.py): a changed palette
    changes every quantized image rendered from it."""
    return _file_mtime(paths.color_model_file)
