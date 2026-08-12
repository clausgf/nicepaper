"""
Hardware descriptions: the palettes a rendered image can be quantized to
(`ColorModel`) and the panel presets the screen editor offers
(`DisplayModel`).

`ColorModel` used to live in GlobalConfig, and deliberately no longer
does -- neither model belongs there. `load_global_config()` copies every
persisted field over the model defaults, so a catalog kept in that file
freezes at whatever it contained when it was first written: palettes or
panels added in a later nicepaper release would never reach an existing
installation, silently. Both catalogs are package resources instead
(see `catalog.py`), versioned with the code, with an optional per-root
file for hardware we don't ship.
"""
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class ColorModel(BaseModel):
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


class DisplayModel(BaseModel):
    """
    A panel preset: the values the screen editor writes into a screen when
    that panel is picked.

    Purely a template. The screen's own fields stay the source of truth
    for rendering and nothing reads the preset again afterwards, so a
    preset that is edited, renamed or removed later never changes how an
    existing screen renders. `ScreenModel.display_id` only records which
    preset was applied last, for the editor.
    """
    id: str
    name: str = Field(description="Name shown in the editor's display list.")
    width: int = Field(description="Panel width in pixels.")
    height: int = Field(description="Panel height in pixels.")
    color_model: str = Field(default="bw", description="Id of the palette this panel can show (see color_models.json).")

    # a preset exists to give a combination that actually works on that
    # panel, so it carries colors rather than leaving them to the global
    # defaults: on a bw panel a red accent would quantize to black anyway,
    # and saying so explicitly beats letting it happen by accident
    color_background: Optional[str] = Field(default=None, description="Screen background color to apply. Empty leaves the global default.")
    color_primary: Optional[str] = Field(default=None, description="Default text/drawing color to apply. Empty leaves the global default.")
    color_accent: Optional[str] = Field(default=None, description="Accent color to apply. Empty leaves the global default.")

    vendor: Optional[str] = Field(default=None, description="Who sells the panel, e.g. 'Waveshare'.")
    gxepd2_class: Optional[str] = Field(
        default=None,
        description=(
            "Matching GxEPD2 display class for the panel, e.g. 'GxEPD2_750_T7'. "
            "Purely informational -- nicepaper renders a PNG and never talks to "
            "the panel driver; this only helps find the right preset for a panel "
            "you know by its firmware class name. Empty when GxEPD2 has no "
            "matching class."
        ),
    )
