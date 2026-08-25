import datetime
from typing import Annotated, ClassVar, List, Optional, Tuple, Union, Literal
from pydantic import BaseModel, Field, model_validator

_DateFormatField = Annotated[
    Optional[str],
    Field(
        default=None,
        description=(
            "Babel/CLDR date pattern, e.g. 'EEEE, dd. MMMM yyyy' renders as "
            "'Monday, 07. July 2026'. Leave empty to use the configured default."
        ),
    ),
]
_TimeFormatField = Annotated[
    Optional[str],
    Field(
        default=None,
        description=(
            "Babel/CLDR time pattern, e.g. 'HH:mm' renders as '14:05'. "
            "Leave empty to use the configured default."
        ),
    ),
]

_ALIGNMENT_PATTERN = r'^[lcr][tcb]$'
# 'lt', not the 'lb' every alignment used to default to: with vertical
# alignment 'b' and no size, text is drawn *above* position_y, so the number
# being edited pointed at the bottom of the text rather than at its top.
# Shared by every widget with an alignment, so they can't drift apart again.
_DEFAULT_ALIGNMENT = "lt"
_ALIGNMENT_DESCRIPTION = (
    "Two-letter alignment code: horizontal (l=left, c=center, r=right) and "
    "vertical (t=top, c=center, b=bottom)."
)
_AlignmentField = Annotated[
    Optional[str],
    Field(pattern=_ALIGNMENT_PATTERN, default=_DEFAULT_ALIGNMENT, description=_ALIGNMENT_DESCRIPTION),
]


class ImageMetadata(BaseModel):
    last_update_at: datetime.datetime
    # expires_at is None when neither an update schedule nor a widget
    # provides a next update time
    expires_at: Optional[datetime.datetime] = None
    version: str


class WidgetModel(BaseModel):
    widget_type: Literal["Text", "Date", "RoomCalendar", "WeatherNow", "WeatherForecast", "WeatherChart",
                         "Image", "HomeAssistant"]

    # Tuple[int, int] fields (position/size) aren't renderable by niceview
    # (an unrecognised field type falls back to a plain ui.input bound to
    # a raw string -- wrong type), so position/size/font are flat scalar
    # fields here instead; `position`/`size`/`font` below are computed
    # properties for the drawing code, not part of the JSON schema.
    position_x: int = Field(description="Horizontal position in pixels from the left edge.")
    position_y: int = Field(description="Vertical position in pixels from the top edge.")
    size_width: Optional[int] = Field(default=None, description="Widget width in pixels. Width and height only take effect together; leave both empty (or 0) for automatic sizing.")
    size_height: Optional[int] = Field(default=None, description="Widget height in pixels. Width and height only take effect together; leave both empty (or 0) for automatic sizing.")
    init_background: Optional[bool] = True
    clipping: Optional[bool] = Field(default=False, description="Cut off content that overflows this widget's size instead of letting it bleed into neighboring widgets.")
    font_name: Optional[str] = Field(default=None, description="Font file name. Leave empty to use the screen's default font name (independent of font size).")
    font_size: Optional[int] = Field(default=None, description="Font size in points. 0 or empty to use the screen's default font size (independent of font name).")
    color_primary: Optional[str] = Field(default=None, description="Text/drawing color for this widget. Leave empty to use the screen's primary color.")
    color_accent: Optional[str] = Field(default=None, description="Accent color for this widget (chart series, gauge fill). Leave empty to use the screen's accent color.")

    # widgets that give a lone width/height a meaning (Image: scale to that
    # dimension, keep aspect ratio) set this True to opt out of the
    # size-pair validation below
    _allows_partial_size: ClassVar[bool] = False

    @model_validator(mode='after')
    def _check_size_pair(self) -> 'WidgetModel':
        # size is all-or-nothing for most widgets (see the size property): a
        # widget is either fully auto-sized (both empty/0) or has a fixed box
        # (both set). A half-filled size used to be silently dropped -- setting
        # only the width had no effect at all -- so reject it here instead,
        # surfacing a visible error in the editor rather than a mystery. bool()
        # treats both None and the 0 that a cleared ui.number round-trips as as
        # "empty", matching the size property below.
        if not self._allows_partial_size and bool(self.size_width) != bool(self.size_height):
            raise ValueError(
                "Set width and height together, or leave both empty for automatic sizing.")
        return self

    @property
    def position(self) -> Tuple[int, int]:
        return (self.position_x, self.position_y)

    @property
    def size(self) -> Optional[Tuple[int, int]]:
        # niceview's ui.number has no clean "empty" state for an
        # Optional[int] -- clearing the field in the browser round-trips
        # as 0, not None -- so 0 has to mean "automatic" too, the same as
        # actually unset, or auto-sizing would silently break the moment
        # a user touches the field without typing a new value
        if not self.size_width or not self.size_height:
            return None
        return (self.size_width, self.size_height)

    @size.setter
    def size(self, value: Optional[Tuple[int, int]]) -> None:
        if value is None:
            self.size_width = None
            self.size_height = None
        else:
            self.size_width, self.size_height = value

    def resolved_font(self, default_name: str, default_size: int) -> Tuple[str, int]:
        """This widget's (font name, size), each aspect falling back to the
        screen default independently: an empty font_name/font_size (or the 0 a
        cleared ui.number round-trips as) takes the default, so a widget can
        override just the name, just the size, or both."""
        return (self.font_name or default_name, self.font_size or default_size)

    def resolved_colors(self, default_primary: str, default_accent: str) -> Tuple[str, str]:
        """This widget's (primary, accent) color, each falling back to the
        screen's independently -- the same per-aspect override as
        resolved_font()."""
        return (self.color_primary or default_primary, self.color_accent or default_accent)


class TextWidgetModel(WidgetModel):
    widget_type: Literal["Text"] = "Text"
    text: str
    alignment: _AlignmentField


class DateWidgetModel(WidgetModel):
    widget_type: Literal["Date"] = "Date"
    date_format: _DateFormatField
    alignment: _AlignmentField


class RoomCalendarWidgetModel(WidgetModel):
    """Shows the room the rendering device is bound to (number, name, notes,
    booking-system calendar) -- see room/backend.py's get_room_events() and
    RoomModel. Room data used to be typed directly into the widget
    (room_number/room_name/ical_url); dropped in favor of the device's own
    room binding, so one screen can serve every room's door sign instead of
    needing one hand-configured screen file per room."""
    widget_type: Literal["RoomCalendar"] = "RoomCalendar"
    date_format_long: _DateFormatField
    date_format: _DateFormatField
    time_format: _TimeFormatField
    # pre-0.20 typed room_number/room_name/ical_url directly into the widget;
    # no explicit migration needed to load an old screen file -- pydantic's
    # default extra='ignore' already drops unknown fields silently.


class WeatherWidgetModel(WidgetModel):
    """Shared fields for the Open-Meteo-backed weather widgets below."""
    latitude: Optional[float] = Field(default=None, description="Latitude of the forecast location, e.g. 52.52. Leave both coordinates empty to use the configured default location.")
    longitude: Optional[float] = Field(default=None, description="Longitude of the forecast location, e.g. 13.405. Leave both coordinates empty to use the configured default location.")

    def resolved_location(self, default_latitude: float,
                          default_longitude: float) -> Optional[Tuple[float, float]]:
        """This widget's (latitude, longitude), or the configured default
        when it has none. None when neither is configured.

        Unlike the font, which falls back per aspect, the fallback is
        all-or-nothing: a location is one value in two fields, so filling
        in half of it must not silently pull the other half from the
        global setting -- that would put the widget somewhere neither
        setting describes.

        "Empty" has to include 0.0, not just None: niceview's ui.number
        round-trips a cleared field as 0 (see the size property above), so
        0 is what an emptied coordinate field actually stores. The cost is
        that exactly 0/0 -- Null Island, in the Gulf of Guinea -- can't be
        addressed; every other coordinate, including the rest of the
        equator and the prime meridian, still can, since only a *pair* of
        zeroes counts as empty."""
        if self.latitude or self.longitude:
            return (self.latitude or 0.0, self.longitude or 0.0)
        if default_latitude or default_longitude:
            return (default_latitude, default_longitude)
        return None


class WeatherNowWidgetModel(WeatherWidgetModel):
    widget_type: Literal["WeatherNow"] = "WeatherNow"


class WeatherForecastWidgetModel(WeatherWidgetModel):
    widget_type: Literal["WeatherForecast"] = "WeatherForecast"
    forecast_hours: int = Field(default=24, description="How many hours ahead the forecast strip covers.")


WeatherMetric = Literal["temperature", "precipitation", "humidity", "pressure", "wind"]


class WeatherChartWidgetModel(WeatherWidgetModel):
    """One configurable chart instead of separate precipitation/temperature
    widgets: primary_metric always drawn (solid, accent-colored, its own
    left Y axis); secondary_metric optional (dashed, black, its own right
    Y axis) -- e.g. temperature + precipitation combined in one chart.
    Which metric renders as bars vs. a line is fixed per metric (only
    precipitation is bursty/mostly-zero enough to read better as bars),
    not separately configurable."""
    widget_type: Literal["WeatherChart"] = "WeatherChart"
    primary_metric: WeatherMetric = Field(default="temperature", description="Always shown; solid line/bars, left Y axis.")
    secondary_metric: Optional[WeatherMetric] = Field(default=None, description="Shown alongside primary_metric if set; dashed, right Y axis.")
    forecast_hours: int = Field(default=24, description="How many hours ahead the chart covers.")
    line_style: Literal["solid", "dashed", "dotted"] = Field(
        default="solid", description="Line style of primary_metric, if it renders as a line "
                                    "(bar metrics ignore this). secondary_metric always stays dashed.")

ImageSourceType = Literal["url", "file"]


class ImageWidgetModel(WidgetModel):
    """Renders an image loaded from a URL or a file in the project directory.

    Unlike other widgets, a lone width/height is meaningful (scale to that
    dimension, keep aspect ratio), so it opts out of the size-pair validation;
    setting both scales to exactly that size. Has no font of its own -- the
    error message (on load failure) uses the screen default font."""
    widget_type: Literal["Image"] = "Image"
    # override the base descriptions: a lone width/height is valid here
    size_width: Optional[int] = Field(default=None, description="Image width in pixels. A single dimension (width or height) scales keeping the aspect ratio; both set scales to exactly that size; empty = natural size.")
    size_height: Optional[int] = Field(default=None, description="Image height in pixels. A single dimension (width or height) scales keeping the aspect ratio; both set scales to exactly that size; empty = natural size.")
    source_type: ImageSourceType = Field(default="url", description="Where the image comes from: a URL, or a file in the project directory.")
    url: Optional[str] = Field(default=None, description="Image URL (used when source_type is 'url').")
    file: Optional[str] = Field(default=None, description="Image file in the project directory (used when source_type is 'file'). Add files there via nice4iot's 'Project Files', or by copying them into the project directory directly.")
    reload_each_time: bool = Field(default=False, description="Reload the image on every render instead of loading it once and caching it.")

    _allows_partial_size: ClassVar[bool] = True


HomeAssistantDisplay = Literal["value", "gauge"]
GaugeStyle = Literal["arc", "bar"]


class HomeAssistantWidgetModel(WidgetModel):
    """Shows one Home Assistant entity's state (or one of its attributes),
    either as a line of text or as a locally drawn gauge.

    The gauge is rendered here with PIL rather than fetched from Home
    Assistant: HA's own gauge cards are browser-rendered and not retrievable
    as an image, and a browser screenshot would dither badly on an e-paper
    palette (see core/gauge.py). An image Home Assistant *does* serve (a
    camera snapshot, an add-on-rendered dashboard) can still be shown with
    the Image widget instead.

    Connection settings (URL, token, intervals) are global, see GlobalConfig."""
    widget_type: Literal["HomeAssistant"] = "HomeAssistant"
    entity_id: str = Field(description="Home Assistant entity id, e.g. 'sensor.living_room_temperature'.")
    attribute: Optional[str] = Field(default=None, description="Show this attribute instead of the entity's state, e.g. 'temperature' of a climate entity. Empty shows the state.")
    label: Optional[str] = Field(default=None, description="Label for the value. Empty uses the entity's friendly name from Home Assistant.")
    unit: Optional[str] = Field(default=None, description="Unit appended to the value. Empty uses the entity's unit_of_measurement from Home Assistant.")
    decimals: int = Field(default=1, ge=0, le=6, description="Decimal places for numeric values. Non-numeric states (e.g. 'on') are shown unchanged.")
    show_label: bool = Field(default=True, description="Draw the label alongside the value.")
    display: HomeAssistantDisplay = Field(default="value", description="Draw the value as a line of text, or as a gauge.")
    alignment: Optional[str] = Field(pattern=_ALIGNMENT_PATTERN, default=_DEFAULT_ALIGNMENT, description=f"{_ALIGNMENT_DESCRIPTION} Only used when display is 'value'.")
    gauge_style: GaugeStyle = Field(default="arc", description="Gauge shape: a 240° dial ('arc') or a horizontal bar. Only used when display is 'gauge'.")
    min_value: float = Field(default=0.0, description="Start of the gauge scale. Values below it are clamped.")
    max_value: float = Field(default=100.0, description="End of the gauge scale. Values above it are clamped.")


# discriminated union: widget_type selects the concrete model and a
# missing/unknown widget_type is a validation error instead of silently
# matching the first union member
AnyWidget = Annotated[
    Union[
        DateWidgetModel, TextWidgetModel, RoomCalendarWidgetModel,
        WeatherNowWidgetModel, WeatherForecastWidgetModel, WeatherChartWidgetModel,
        ImageWidgetModel, HomeAssistantWidgetModel,
    ],
    Field(discriminator="widget_type"),
]


class ScreenModel(BaseModel):
    """
    One screen: its canvas, the palette it is served in, and its widgets.

    A screen is bound to one panel, so everything the panel decides lives
    here rather than being negotiated per request. `panel_type_id` records
    which panel type (see catalog/models.py's PanelTypeModel) filled these
    fields in the editor, but is never read back at render time -- the fields
    below are the source of truth, and stay editable afterwards.
    """
    # Tuple[int, int] -- see the same note on WidgetModel above.
    width: int = Field(description="Canvas width in pixels.")
    height: int = Field(description="Canvas height in pixels.")
    panel_type_id: Optional[str] = Field(
        default=None,
        description=(
            "Id of the panel type last applied to this screen. A "
            "reminder of which panel this screen is laid out for; picking "
            "one fills in the size, palette and colors below, which then "
            "stay editable and are what actually gets rendered."
        ),
    )
    palette_id: Optional[str] = Field(
        default=None,
        description=(
            "Id of the palette the image is quantized to before "
            "it is served, e.g. 'bwr'. Leave empty to serve the unquantized "
            "RGB image (the display then has to quantize it itself)."
        ),
    )
    color_background: Optional[str] = Field(default=None, description="Background color of this screen. Leave empty to use the global default.")
    color_primary: Optional[str] = Field(default=None, description="Default text/drawing color of this screen. Leave empty to use the global default.")
    color_accent: Optional[str] = Field(default=None, description="Accent color of this screen (chart series, gauge fill). Leave empty to use the global default.")
    update_schedule_id: Optional[str] = Field(
        default="default",
        description=(
            "Name of a schedule file (without .json) that determines when "
            "this screen expires and is re-rendered. Leave empty to only "
            "re-render on request or when a widget provides its own "
            "expiry (e.g. RoomCalendar's next event)."
        ),
    )
    widgets: List[AnyWidget] = []

    @property
    def size(self) -> Tuple[int, int]:
        return (self.width, self.height)

    def resolved_colors(self, default_background: str, default_primary: str,
                        default_accent: str) -> Tuple[str, str, str]:
        """This screen's (background, primary, accent) color, each falling
        back to the global default independently -- the same per-aspect
        override WidgetModel.resolved_colors() then applies once more on
        top, for a single widget."""
        return (self.color_background or default_background,
                self.color_primary or default_primary,
                self.color_accent or default_accent)
