"""
The panel-type and palette catalogs.

Both ship as package resources (`resources/panel_types.json`,
`resources/palettes.json`) so they are versioned with the code and a
new nicepaper release actually reaches existing installations -- see
`catalog/models.py` for why neither belongs in GlobalConfig. Each can be
extended per data root by a file of the same name in `paths.root`
(`data/panel_types.json` standalone, `<project>/.epaper/panel_types.json` as a
nice4iot extension): entries are merged by id, the root file wins, so a
root file can both add hardware we don't ship and correct an entry we do.

Only the palettes matter at render time -- a screen stores the *values*
a panel-type preset gave it, not a reference to the preset, so editing
`panel_types.json` never changes an existing screen's image. Editing
`palettes.json` does, hence `palettes_mtime()` for the render
cache (see screen/backend.py).
"""
import importlib.resources
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import TypeAdapter

from extensions.epaper.catalog.models import Palette, PanelTypeModel
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.util import logger

__all__ = [
    "get_palettes", "get_palette", "get_panel_types", "get_panel_type",
    "palettes_mtime", "nearest_palette_color", "panel_type_label",
]

_PALETTES_RESOURCE = "palettes.json"
_PANEL_TYPES_RESOURCE = "panel_types.json"

_palettes_adapter = TypeAdapter(List[Palette])
_panel_types_adapter = TypeAdapter(List[PanelTypeModel])

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
        # explicit "extensions.epaper", not __package__: this module now lives
        # in the catalog sub-package, but resources/ is shared, one level up
        text = (importlib.resources.files("extensions.epaper") / "resources" / resource).read_text(encoding="utf-8")
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


def get_palettes(paths: Optional[EpaperPaths] = None) -> Dict[str, Palette]:
    """All known palettes by id. `paths` adds/overrides them from that
    root's palettes.json; omit it where no root is in scope."""
    builtin = _builtin(_PALETTES_RESOURCE, _palettes_adapter)
    overlay = _overlay(paths.palettes_file, _palettes_adapter) if paths else []
    return _merged(builtin, overlay)


def get_palette(id: Optional[str], paths: Optional[EpaperPaths] = None) -> Optional[Palette]:
    """The palette with this id, or None for an empty/unknown id -- which
    callers treat as 'don't quantize', i.e. serve the RGB image."""
    if not id:
        return None
    palette = get_palettes(paths).get(id)
    if palette is None:
        logger.warning(f"Unknown palette {id!r}, serving the unquantized image instead")
    return palette


def get_panel_types(paths: Optional[EpaperPaths] = None) -> Dict[str, PanelTypeModel]:
    """All known panel-type presets by id, root entries merged in as above."""
    builtin = _builtin(_PANEL_TYPES_RESOURCE, _panel_types_adapter)
    overlay = _overlay(paths.panel_types_file, _panel_types_adapter) if paths else []
    return _merged(builtin, overlay)


def get_panel_type(id: Optional[str], paths: Optional[EpaperPaths] = None) -> Optional[PanelTypeModel]:
    """The panel-type preset with this id, or None if it is empty/unknown. An
    unknown id is not an error: presets are only a template, and a screen
    that references one that has since been removed still renders from
    its own fields."""
    if not id:
        return None
    return get_panel_types(paths).get(id)


def panel_type_label(panel_type: PanelTypeModel) -> str:
    """Option label for a panel-type select: `panel_id` first (the
    manufacturer's own designation, distinguishing same-hardware rebrands
    that share it, see PanelTypeModel.panel_id) then this catalog entry's
    own name, since a `ui.select`'s value is already the catalog id -- the
    label needs the info that id doesn't carry."""
    return f'{panel_type.panel_id} {panel_type.name}' if panel_type.panel_id else panel_type.name


def palettes_mtime(paths: EpaperPaths) -> Optional[float]:
    """mtime of this root's palettes.json, or None if it has none."""
    return _file_mtime(paths.palettes_file)


def nearest_palette_color(rgb: Tuple[int, int, int], palette: Palette, *,
                          exclude_white: bool = True) -> Tuple[int, int, int]:
    """The palette entry closest to rgb (Euclidean distance in RGB space).

    A widget that wants to draw a *solid* color the display can render exactly
    (e.g. a category-color card outline) needs this instead of relying on the
    final whole-image quantize() (core/imagecache.py): that step dithers, which
    looks fine for photographic content but ugly on thin lines/text -- picking
    the nearest palette member up front draws it as a flat, undithered color.

    exclude_white drops (255, 255, 255) from the candidates when at least one
    other entry remains, since white is the background on every shipped
    palette and a color "approximated to white" would just vanish."""
    candidates = palette.palette
    if exclude_white:
        non_white = [c for c in candidates if c != (255, 255, 255)]
        if non_white:
            candidates = non_white

    def distance(c: Tuple[int, int, int]) -> int:
        return (c[0] - rgb[0]) ** 2 + (c[1] - rgb[1]) ** 2 + (c[2] - rgb[2]) ** 2

    return min(candidates, key=distance)
