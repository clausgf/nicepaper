"""
Hardware descriptions: the palettes a rendered image can be quantized to
(`Palette`) and the panel-type presets the screen editor offers
(`PanelTypeModel`).

`Palette` used to live in GlobalConfig, and deliberately no longer
does -- neither model belongs there. `load_global_config()` copies every
persisted field over the model defaults, so a catalog kept in that file
freezes at whatever it contained when it was first written: palettes or
panels added in a later nicepaper release would never reach an existing
installation, silently. Both catalogs are package resources instead
(see `catalog/backend.py`), versioned with the code, with an optional
per-root file for hardware we don't ship.
"""
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class Palette(BaseModel):
    """
    A palette an e-paper panel can display. The screen is always rendered
    in RGB first and quantized to this palette before it is served, so
    the palette decides what dithers and what doesn't -- a drawing color
    that is an exact palette member survives unchanged.
    """
    id: str
    name: str
    palette: List[Tuple[int, int, int]]
    background_color_index: int = 1


class PanelTypeModel(BaseModel):
    """
    A panel-type preset: the values the screen editor writes into a screen
    when that panel type is picked.

    Purely a template. The screen's own fields stay the source of truth
    for rendering and nothing reads the preset again afterwards, so a
    preset that is edited, renamed or removed later never changes how an
    existing screen renders. `ScreenModel.panel_type_id` only records which
    panel type was applied last, for the editor.
    """
    id: str
    name: str = Field(description="Name shown in the editor's panel-type list.")
    width: int = Field(description="Panel width in pixels.")
    height: int = Field(description="Panel height in pixels.")
    palette_id: str = Field(default="bw", description="Id of the palette this panel can show (see palettes.json).")

    color_background: str = Field(default="#ffffff", description="Screen background color to apply.")

    vendor: Optional[str] = Field(default=None, description="Who sells the panel, e.g. 'Waveshare'.")
    panel_id: Optional[str] = Field(
        default=None,
        description=(
            "The panel's own official designation from its manufacturer's "
            "datasheet, e.g. 'GDEH075Z9' -- not a GxEPD2 (Arduino library) "
            "class name, and not this catalog entry's own `id` (which is a "
            "vendor+size slug, one per vendor SKU). The same physical panel is "
            "often sold under different vendor names (e.g. Waveshare and Seeed "
            "both rebrand Good Display panels) -- those get separate catalog "
            "entries with the same panel_id, so this is the field that "
            "identifies the underlying hardware across vendor listings. Purely "
            "informational -- nicepaper renders a PNG and never talks to the "
            "panel driver; this only helps find the right preset for a panel "
            "you know by its firmware/datasheet designation. Empty when unknown."
        ),
    )
