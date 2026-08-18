from typing import Optional, Tuple
from pydantic import BaseModel, Field


class GlobalConfig(BaseModel):
    """
    Settings that are the same for every screen regardless of which
    project/root it belongs to -- JSON-persisted and editable via a single
    card (ui/global_settings.py), unlike the old env-var-based
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

    The palette catalog (epaper_color_models) used to live here too and
    has moved to a package resource -- see models/display.py: this file
    is copied over the model defaults on load, so anything catalog-shaped
    kept here freezes at whatever an installation wrote once and never
    picks up entries added in a later release. An old config file that
    still contains the field loads fine (pydantic ignores it) and drops
    it on the next save.

    The three colors below stay: they are the *defaults*, applied where a
    screen (and, within a screen, a widget) doesn't set its own.
    """
    ical_update_interval_s: int = 600
    ical_max_days: int = 30
    ical_error: str = "Error fetching calendar data"
    no_appointments: str = "No appointments"
    next_appointment: str = "Next appointment"
    current_appointment: str = "Current appointment"
    further_appointments: str = "Further appointments"
    roomcalendar_date_format_long: str = "EEEE, dd.MM.yyyy"
    roomcalendar_date_format_short: str = "dd.MM.yy"
    roomcalendar_time_format: str = "HH:mm"

    weather_update_interval_s: int = 900
    weather_error: str = "Error fetching weather data"
    latitude: float = Field(default=52.52, description="Default latitude for weather widgets that set no location of their own.")
    longitude: float = Field(default=13.405, description="Default longitude for weather widgets that set no location of their own.")
    wind_speed_unit: str = Field(
        default="kmh",
        description=(
            "Unit for wind speed: kmh, ms, mph or kn (knots). Open-Meteo is "
            "always fetched in km/h and converted locally, so changing this "
            "needs no refetch."
        ),
    )
    weather_retry_min_s: int = Field(default=60, description="Backoff after a failed weather fetch starts at this many seconds and doubles per consecutive failure.")
    weather_retry_max_s: int = Field(default=1800, description="Upper cap for the weather-fetch backoff, in seconds.")
    weather_stale_notice: str = Field(default="as of {time}", description="WeatherNow marker shown when serving cached data during an outage; '{time}' is the last successful update. Empty to hide.")

    image_error: str = "Error loading image"

    # Home Assistant (HomeAssistant widget). The token is a secret stored in
    # plain text in this config file, like every other field -- see SECURITY.md;
    # give it a read-only user's long-lived access token if that matters.
    homeassistant_url: str = Field(default="", description="Base URL of the Home Assistant instance, e.g. 'http://homeassistant.local:8123'. Empty disables the HomeAssistant widget.")
    homeassistant_token: str = Field(default="", description="Long-lived access token, created on the Home Assistant profile page. Stored in plain text in this config file.")
    homeassistant_update_interval_s: int = Field(default=300, description="How long a fetched entity state is reused before Home Assistant is asked again.")
    homeassistant_retry_min_s: int = Field(default=60, description="Backoff after a failed Home Assistant fetch starts at this many seconds and doubles per consecutive failure.")
    homeassistant_retry_max_s: int = Field(default=1800, description="Upper cap for the Home Assistant fetch backoff, in seconds.")
    homeassistant_error: str = "Error fetching Home Assistant data"
    homeassistant_stale_notice: str = Field(default="as of {time}", description="HomeAssistant widget marker shown when serving a cached value during an outage; '{time}' is the last successful update. Empty to hide.")

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
            "Accent color for the chart widgets' primary series and the "
            "gauge fill. Red is the only accent the bwr palette has besides "
            "black/white, and an exact member of c7/e6 too. A screen or a "
            "widget can override it -- a display preset for a black/white "
            "panel does, since red would only quantize to black there."
        ),
    )

    @property
    def font(self) -> Tuple[str, int]:
        return (self.font_name, self.font_size)
