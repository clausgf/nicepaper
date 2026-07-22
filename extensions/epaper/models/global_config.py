from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class ColorModel(BaseModel):
    """
    Color model for the e-paper display.
    """
    id: str
    name: str
    palette: List[Tuple[int, int, int]]
    background_color_index: int = 1


class GlobalConfig(BaseModel):
    """
    Settings that are the same for every screen regardless of which
    project/root it belongs to -- JSON-persisted and editable via a single
    card (panels.global_config_card()), unlike the old env-var-based
    pydantic-settings Config: nice4iot's register_global_card() and the
    standalone "Global" tab both need something a user can actually edit
    and save, not just override at process startup.

    font_path/icon_path (package resource locations) deliberately stay
    out of this model -- see config.py's _ResourcePaths -- since they are
    installation-specific derived paths, not user settings, and persisting
    a stale absolute path across an upgrade/redeploy would silently break
    font/icon loading; they're also cached into separate objects at import
    time in drawingcontext.py, so editing them here at runtime wouldn't
    even take effect without further changes.

    position/size/font on WidgetModel taught the same lesson already:
    niceview can't render a Tuple field (falls back to a plain ui.input
    bound to a raw string -- wrong type). `font` here is flattened into
    font_name/font_size the same way. Colors are simpler: PIL accepts hex
    color strings directly everywhere a fill/color is currently passed
    (verified), so color_background/color_primary/color_accent are plain
    hex strings rendered via niceview's native ui.color_input widget,
    no tuple at all -- nicer than a 3-number-field flatten would have been.
    """
    ical_update_interval_s: int = 600
    ical_max_days: int = 30
    ical_error: str = "Fehler beim Abrufen der Kalenderdaten"
    no_appointments: str = "Keine Termine"
    next_appointment: str = "Nächster Termin"
    current_appointment: str = "Aktueller Termin"
    further_appointments: str = "Weitere Termine"
    roomcalendar_date_format_long: str = "EEEE, dd.MM.yyyy"
    roomcalendar_date_format_short: str = "dd.MM.yy"
    roomcalendar_time_format: str = "HH:mm"

    weather_update_interval_s: int = 900
    weather_error: str = "Fehler beim Abrufen der Wetterdaten"
    wind_speed_unit: str = Field(
        default="kmh",
        description=(
            "Unit the WeatherNow widget shows wind speed in: kmh, ms, mph or "
            "kn (knots). Open-Meteo is always fetched in km/h and converted "
            "locally, so changing this needs no refetch. Weather description "
            "language follows the 'locale' field (de/en)."
        ),
    )

    locale: str = 'de_DE.utf8'
    timezone: str = 'Europe/Berlin'
    date_format: str = 'dd.MM.yy'
    time_format: str = 'HH:mm'

    font_name: str = Field(default="Ubuntu-Regular.ttf", description="Default font file name for widgets without their own font.")
    font_size: int = Field(default=16, description="Default font size for widgets without their own font.")

    # required, unlike color_accent below: there's no "or fallback" for
    # these two anywhere they're used (Image.new(color=...) etc.), so an
    # emptied field must be rejected by niceview's own required-field
    # validation rather than silently breaking every render
    color_background: str = Field(default="#ffffff", description="Screen background color.")
    color_primary: str = Field(default="#000000", description="Default text/drawing color.")
    color_accent: Optional[str] = Field(
        default="#ff0000",
        description=(
            "Chart widgets' primary-series color. Red is the only accent "
            "the bwr color model has besides black/white, and an exact "
            "palette member of c7/e6 too, so it never dithers regardless "
            "of which color_model a display requests."
        ),
    )

    # not exposed in global_config_card() (a nested list of models with a
    # nested list of tuples is well beyond what niceview can render), kept
    # here only so it round-trips through the JSON file like every other
    # field
    epaper_color_models: List[ColorModel] = [
        ColorModel(id='bw', name='Black on white', palette=[(0, 0, 0), (255, 255, 255)]),
        ColorModel(id='bwr', name='Black/Red on white', palette=[(0, 0, 0), (255, 255, 255), (255, 0, 0)]),
        ColorModel(id='gs4', name='4-Greyscale on white', palette=[(0, 0, 0), (255, 255, 255), (128, 128, 128), (192, 192, 192)]),
        ColorModel(id='c7', name='7-color C7', palette=[(0, 0, 0), (255, 255, 255), (0, 255, 0), (0, 0, 255), (255, 0, 0), (255, 255, 0), (255, 165, 0)]),
        ColorModel(id='e6', name='Spectra E6', palette=[(0, 0, 0), (255, 255, 255), (255, 255, 0), (255, 0, 0), (0, 0, 255), (0, 255, 0)]),
    ]

    @property
    def font(self) -> Tuple[str, int]:
        return (self.font_name, self.font_size)
