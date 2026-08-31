import datetime
from typing import Annotated, ClassVar, List, Optional, Tuple, Union, Literal

import niceview
from pydantic import BaseModel, Field, field_validator, model_validator

_DATE_FORMAT_DESCRIPTION = (
    "Babel/CLDR date pattern, e.g. 'EEEE, dd. MMMM yyyy' renders as "
    "'Monday, 01. July 2026'. 'dd.MM.yy' renders as '01.07.26'. "
    "Leave empty to use the configured default."
)
_DateFormatField = Annotated[
    Optional[str],
    Field(default=None, description=_DATE_FORMAT_DESCRIPTION),
    niceview.Field(),
]
# Same as _DateFormatField, with a short-form hint (used next to a time).
_ShortDateFormatField = Annotated[
    Optional[str],
    Field(default=None, description=_DATE_FORMAT_DESCRIPTION),
    niceview.Field(),
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
    niceview.Field(),
]

_ALIGNMENT_PATTERN = r'^[lcr][tcb]$'
_DEFAULT_ALIGNMENT = "lt"
_ALIGNMENT_DESCRIPTION = (
    "Two-letter alignment code, e.g. 'lt': horizontal (l=left, c=center, r=right) and "
    "vertical (t=top, c=center, b=bottom)."
)
_AlignmentField = Annotated[
    Optional[str],
    Field(pattern=_ALIGNMENT_PATTERN, default=_DEFAULT_ALIGNMENT, description=_ALIGNMENT_DESCRIPTION),
    niceview.Field(classes='w-32'),
]


class ImageMetadata(BaseModel):
    last_update_at: datetime.datetime
    # None if neither an update schedule nor a widget provides a next update time
    expires_at: Optional[datetime.datetime] = None
    version: str


class WidgetModel(BaseModel):
    widget_type: Literal["Text", "Date", "Box", "Line", "RoomCalendar", "WeatherNow", "WeatherForecast",
                         "WeatherChart", "Image", "HomeAssistant"]

    position_x: Annotated[int, Field(description="Horizontal position in pixels from the left edge.")]
    position_y: Annotated[int, Field(description="Vertical position in pixels from the top edge.")]
    size_width: Annotated[Optional[int], Field(
        description="Widget width in pixels. Width and height only take effect together; "
                    "leave both empty (or 0) for automatic sizing.")] = None
    size_height: Annotated[Optional[int], Field(
        description="Widget height in pixels. Width and height only take effect together; "
                    "leave both empty (or 0) for automatic sizing.")] = None
    init_background: Annotated[Optional[bool], Field(
        description="Fill this widget's box with color_background before drawing. Off draws directly "
                    "onto whatever is already there (the screen background, or an earlier, overlapping "
                    "widget) -- e.g. a highlighted panel behind the widget's content needs this on."
    )] = False
    clipping: Annotated[Optional[bool], Field(
        description="Cut off content that overflows this widget's size instead of letting it bleed "
                    "into neighboring widgets.")] = False
    font_name: Annotated[Optional[str], Field(
        description="Font file name. Leave empty to use the screen's default font name "
                    "(independent of font size).")] = None
    font_size: Annotated[Optional[int], Field(
        description="Font size in points. 0 or empty to use the screen's default font size "
                    "(independent of font name).")] = None
    color_primary: Annotated[str, Field(description="Text/drawing color for this widget.")] = "#000000"
    color_background: Annotated[str, Field(
        description="Background color for this widget's box. Only visible when init_background "
                    "is set.")] = "#ffffff"

    # Image scales a lone width/height instead of requiring both; opts out below.
    _allows_partial_size: ClassVar[bool] = False

    @field_validator('color_primary', 'color_background', mode='before')
    @classmethod
    def _null_uses_the_default(cls, value, info):
        """Pre-0.28 screens could have this explicitly null (old
        inherit-from-screen chain); treat that like the key being absent."""
        return cls.model_fields[info.field_name].default if value is None else value

    @model_validator(mode='after')
    def _check_size_pair(self) -> 'WidgetModel':
        # size is all-or-nothing for most widgets: reject a half-filled size
        # instead of silently dropping it (bool() treats 0 as empty too, see size below)
        if not self._allows_partial_size and bool(self.size_width) != bool(self.size_height):
            raise ValueError(
                "Set width and height together, or leave both empty for automatic sizing.")
        return self

    @property
    def position(self) -> Tuple[int, int]:
        return (self.position_x, self.position_y)

    @property
    def size(self) -> Optional[Tuple[int, int]]:
        # a cleared ui.number round-trips as 0, not None, so 0 means "automatic" too
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
        """(font name, size), each falling back to the default independently."""
        return (self.font_name or default_name, self.font_size or default_size)


class TextWidgetModel(WidgetModel):
    widget_type: Literal["Text"] = "Text" # pyright: ignore[reportIncompatibleVariableOverride]
    text: Annotated[str, Field(description="The text to display.")] = "Text"
    alignment: _AlignmentField


class DateWidgetModel(WidgetModel):
    widget_type: Literal["Date"] = "Date" # pyright: ignore[reportIncompatibleVariableOverride]
    date_format: _DateFormatField
    alignment: _AlignmentField


class BoxWidgetModel(WidgetModel):
    """A rectangle: outline (color_primary, line_width) and/or fill
    (color_background, via init_background). Draws its own fill+outline as
    one shape (core/widgets/box.py) rather than through the base class's
    generic square fill, since a rounded corner_radius needs both to follow
    the same rounded path."""
    widget_type: Literal["Box"] = "Box" # pyright: ignore[reportIncompatibleVariableOverride]
    size_width: Annotated[Optional[int], Field(description="Box width in pixels.")] = 100
    size_height: Annotated[Optional[int], Field(description="Box height in pixels.")] = 60
    color_primary: Annotated[str, Field(description="Border color.")] = "#000000"
    line_width: Annotated[int, Field(ge=0,
        description="Border stroke width in pixels. 0 draws no border -- useful with "
                    "init_background alone for a plain filled panel.")] = 1
    corner_radius: Annotated[Optional[int], Field(ge=0,
        description="Corner radius in pixels for rounded corners. Empty or 0 for square "
                    "corners.")] = None


class LineWidgetModel(WidgetModel):
    """A straight line from the widget's position to position+size: leave
    size_height empty for a horizontal line, size_width empty for a
    vertical one, or set both for a diagonal. Opts out of the size-pair
    validation for the same reason Image does -- one dimension alone is
    meaningful here, not an error."""
    widget_type: Literal["Line"] = "Line" # pyright: ignore[reportIncompatibleVariableOverride]
    size_width: Annotated[Optional[int], Field(
        description="Horizontal length in pixels. Leave empty (with size_height set) for a "
                    "vertical line.")] = 100
    size_height: Annotated[Optional[int], Field(
        description="Vertical length in pixels. Leave empty (with size_width set) for a "
                    "horizontal line.")] = None
    color_primary: Annotated[str, Field(description="Line color.")] = "#000000"
    line_width: Annotated[int, Field(ge=1, description="Line stroke width in pixels.")] = 2
    line_style: Annotated[Literal["solid", "dashed", "dotted"], Field(
        description="Line style.")] = "solid"

    _allows_partial_size: ClassVar[bool] = True


class RoomCalendarWidgetModel(WidgetModel):
    """Shows the rendering device's own bound room (see room/backend.py's
    get_room_events()), not a hand-configured room_number/room_name/ical_url."""
    widget_type: Literal["RoomCalendar"] = "RoomCalendar" # pyright: ignore[reportIncompatibleVariableOverride]
    date_format_long: _DateFormatField
    date_format: _ShortDateFormatField
    time_format: _TimeFormatField
    # old room_number/room_name/ical_url fields: dropped silently by pydantic's extra='ignore'


class WeatherWidgetModel(WidgetModel):
    """Shared fields for the Open-Meteo-backed weather widgets below."""
    latitude: Annotated[Optional[float], Field(
        description="Latitude of the forecast location, e.g. 52.52. Leave both coordinates "
                    "empty to use the configured default location."),
        niceview.Field(hint='Both empty = default location', clearable=True)] = None
    longitude: Annotated[Optional[float], Field(
        description="Longitude of the forecast location, e.g. 13.405. Leave both coordinates "
                    "empty to use the configured default location."),
        niceview.Field(hint='Both empty = default location', clearable=True)] = None

    def resolved_location(self, default_latitude: float,
                          default_longitude: float) -> Optional[Tuple[float, float]]:
        """(latitude, longitude): this widget's own, else the default, else
        None. All-or-nothing fallback, unlike font -- half a location would
        put the widget somewhere neither setting describes. 0.0 counts as
        empty (a cleared ui.number), so exact 0/0 can't be addressed."""
        if self.latitude or self.longitude:
            return (self.latitude or 0.0, self.longitude or 0.0)
        if default_latitude or default_longitude:
            return (default_latitude, default_longitude)
        return None


class WeatherNowWidgetModel(WeatherWidgetModel):
    widget_type: Literal["WeatherNow"] = "WeatherNow" # pyright: ignore[reportIncompatibleVariableOverride]


class WeatherForecastWidgetModel(WeatherWidgetModel):
    widget_type: Literal["WeatherForecast"] = "WeatherForecast" # pyright: ignore[reportIncompatibleVariableOverride]
    forecast_hours: Annotated[int, 
                              Field(description="How many hours ahead the forecast strip covers."), 
                              niceview.Field(hint="Number of hours to show.")] = 24


WeatherMetric = Literal["temperature", "precipitation", "humidity", "pressure", "wind"]


class WeatherChartWidgetModel(WeatherWidgetModel):
    """One configurable chart: primary_metric (left axis) + optional
    secondary_metric (dashed, right axis). Either left empty draws no trace."""
    widget_type: Literal["WeatherChart"] = "WeatherChart" # pyright: ignore[reportIncompatibleVariableOverride]
    primary_metric: Annotated[Optional[WeatherMetric], Field(
        description="Solid line/bars, left Y axis. Empty draws no primary trace."),
        niceview.Field(clearable=True)] = "temperature"
    secondary_metric: Annotated[Optional[WeatherMetric], Field(
        description="Dashed, right Y axis. Empty draws no secondary trace."),
        niceview.Field(clearable=True)] = None
    forecast_hours: Annotated[int, 
                              Field(description="How many hours ahead the chart covers."),
                              niceview.Field(hint="Number of hours to show.")] = 24
    # a plain Literal is already auto-rendered as ui.select with these options
    line_style_primary: Annotated[Literal["solid", "dashed", "dotted"], Field(
        description="Line style of primary metric, if it renders as a line "
                    "(bar metrics ignore this).")] = "solid"
    line_style_secondary: Annotated[Literal["solid", "dashed", "dotted"], Field(
        description="Line style of secondary metric, if it renders as a line "
                    "(bar metrics ignore this).")] = "dashed"
    # rendered as a compact swatch, not through ModelForm -- see WIDGET_TYPES
    color_primary_series: Annotated[str, Field(
        description="Color of primary_metric's trace and axis title. On a bwr/c7/e6 panel, set "
                    "this to the panel's accent (e.g. red) to highlight it.")] = "#000000"
    color_secondary_series: Annotated[str, Field(
        description="Color of secondary_metric's trace and axis title. Distinguished from the "
                    "primary trace by its dashed line style even when this is the same color."
    )] = "#000000"

ImageSourceType = Literal["url", "file"]


class ImageWidgetModel(WidgetModel):
    """An image loaded from a URL or a project file. Unlike other widgets, a
    lone width/height scales the image (keeping aspect ratio), so it opts
    out of the size-pair validation."""
    widget_type: Literal["Image"] = "Image" # pyright: ignore[reportIncompatibleVariableOverride]
    size_width: Annotated[Optional[int], Field(
        description="Image width in pixels. A single dimension (width or height) scales keeping "
                    "the aspect ratio; both set scales to exactly that size; empty = natural size."
    )] = None
    size_height: Annotated[Optional[int], Field(
        description="Image height in pixels. A single dimension (width or height) scales keeping "
                    "the aspect ratio; both set scales to exactly that size; empty = natural size."
    )] = None
    source_type: Annotated[ImageSourceType, Field(
        description="Where the image comes from: a URL, or a file in the project directory."),
        niceview.Field(widget_type='ui.toggle', label='')] = "url"
    url: Annotated[Optional[str], Field(description="Image URL (used when source_type is 'url').")] = None
    file: Annotated[Optional[str], Field(
        description="Image file in the project directory (used when source_type is 'file'). Add "
                    "files there via nice4iot's 'Project Files', or by copying them into the project "
                    "directory directly.")] = None
    reload_each_time: Annotated[bool, Field(
        description="Reload the image on every render instead of loading it once and caching it."),
        niceview.Field(label='Reload on every rendering')] = False

    _allows_partial_size: ClassVar[bool] = True


HomeAssistantDisplay = Literal["value", "arc", "bar"]


class HomeAssistantWidgetModel(WidgetModel):
    """One Home Assistant entity's state (or an attribute of it), as text or
    a locally drawn gauge (see core/gauge.py -- HA's own gauge cards aren't
    retrievable as an image). Connection settings live in GlobalConfig."""
    widget_type: Literal["HomeAssistant"] = "HomeAssistant" # pyright: ignore[reportIncompatibleVariableOverride]
    entity_id: Annotated[str, Field(description="Home Assistant entity id, e.g. "
                                    "'sensor.living_room_temperature'.")] = "sensor.example"
    attribute: Annotated[Optional[str], Field(
        description="Show this attribute instead of the entity's state, e.g. 'temperature' of a "
                    "climate entity. Empty shows the state.")] = None
    label: Annotated[Optional[str], Field(
        description="Label for the value. Empty uses the entity's friendly name from Home "
                    "Assistant.")] = None
    unit: Annotated[Optional[str], Field(
        description="Unit appended to the value. Empty uses the entity's unit_of_measurement "
                    "from Home Assistant.")] = None
    decimals: Annotated[int, Field(ge=0, le=6,
        description="Decimal places for numeric values. Non-numeric states (e.g. 'on') are "
                    "shown unchanged."),
        niceview.Field(classes='w-32')] = 1
    show_label: Annotated[bool, Field(description="Draw the label alongside the value."), niceview.Field(label="")] = True
    display: Annotated[HomeAssistantDisplay, Field(
        description="Draw the value as a line of text ('value'), or as a gauge -- a 240° dial "
                    "('arc') or a horizontal bar ('bar')."),
        niceview.Field(widget_type='ui.toggle', label="",
                       options={'value': 'Value', 'arc': 'Arc', 'bar': 'Bar'})] = "value"
    min_value: Annotated[float, Field(description="Start of the gauge scale. Values below it "
                                      "are clamped. Only used when display is 'arc' or 'bar'."
                                      )] = 0.0
    max_value: Annotated[float, Field(description="End of the gauge scale. Values above it "
                                      "are clamped. Only used when display is 'arc' or 'bar'."
                                      )] = 100.0
    # rendered as a compact swatch, not through ModelForm -- see WIDGET_TYPES
    color_fill: Annotated[str, Field(
        description="Fill color of the filled part of the gauge. Only used when display is "
                    "'arc' or 'bar'.")] = "#000000"


# discriminated union: an unknown widget_type is a validation error,
# not a silent match on the first union member
AnyWidget = Annotated[
    Union[
        DateWidgetModel, TextWidgetModel, BoxWidgetModel, LineWidgetModel, RoomCalendarWidgetModel,
        WeatherNowWidgetModel, WeatherForecastWidgetModel, WeatherChartWidgetModel,
        ImageWidgetModel, HomeAssistantWidgetModel,
    ],
    Field(discriminator="widget_type"),
]


class ScreenModel(BaseModel):
    """One screen: its canvas, palette and widgets. `panel_type_id` just
    records which panel filled these fields in the editor -- the fields
    themselves are the source of truth at render time, and stay editable."""
    panel_type_id: Optional[str] = Field(
        default=None,
        description=(
            "Id of the panel type last applied to this screen. A "
            "reminder of which panel this screen is laid out for; picking "
            "one fills in the size, palette and colors below, which then "
            "stay editable and are what actually gets rendered."
        ),
    )
    width: int = Field(description="Canvas width in pixels.")
    height: int = Field(description="Canvas height in pixels.")
    palette_id: Annotated[str, Field(
            title='Palette',
            description=
                "Id of the palette the image is quantized to before it is "
                "served, e.g. 'bwr'. Set to '' (an unknown id also works) to "
                "serve the unquantized RGB image instead.",
        )] = 'bw'
    color_background: str = Field(default="#ffffff", description="Background color of this screen's canvas.")

    @field_validator('color_background', 'palette_id', mode='before')
    @classmethod
    def _null_uses_the_default(cls, value, info):
        """Same as WidgetModel's own _null_uses_the_default."""
        return cls.model_fields[info.field_name].default if value is None else value

    update_schedule_id: Annotated[Optional[str], Field(
        title="Update Schedule",
        description=
            "Name of a schedule file (without .json) that determines when "
            "this screen expires and is re-rendered. Leave empty to only "
            "re-render on request or when a widget provides its own "
            "expiry (e.g. RoomCalendar's next event).",
    )] = "default"
    widgets: List[AnyWidget] = []

    @property
    def size(self) -> Tuple[int, int]:
        return (self.width, self.height)
