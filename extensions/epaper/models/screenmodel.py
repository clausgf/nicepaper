import datetime
from typing import Annotated, List, Optional, Tuple, Union, Literal
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


class ImageMetadata(BaseModel):
    last_update_at: datetime.datetime
    # expires_at is None when neither an update schedule nor a widget
    # provides a next update time
    expires_at: Optional[datetime.datetime] = None
    version: str


class WidgetModel(BaseModel):
    widget_type: Literal["Text", "Date", "RoomCalendar", "WeatherNow", "WeatherForecast", "WeatherChart"]

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
    show_bounding_box: Optional[bool] = Field(default=False, description="Draw an outline around this widget's box. Useful while laying out a screen.")
    font_name: Optional[str] = Field(default=None, description="Font file name. Leave empty to use the screen's default font.")
    font_size: Optional[int] = Field(default=None, description="Font size in points. 0 or empty to use the screen's default font.")

    @model_validator(mode='after')
    def _check_size_pair(self) -> 'WidgetModel':
        # size is all-or-nothing (see the size property): a widget is either
        # fully auto-sized (both empty/0) or has a fixed box (both set). A
        # half-filled size used to be silently dropped -- setting only the
        # width had no effect at all -- so reject it here instead, surfacing
        # a visible error in the editor rather than a mystery. bool() treats
        # both None and the 0 that a cleared ui.number round-trips as as
        # "empty", matching the size property below.
        if bool(self.size_width) != bool(self.size_height):
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

    @property
    def font(self) -> Optional[Tuple[str, int]]:
        # same 0-vs-None quirk as size above, for font_size
        if not self.font_name or not self.font_size:
            return None
        return (self.font_name, self.font_size)


class TextWidgetModel(WidgetModel):
    widget_type: Literal["Text"] = "Text"
    text: str
    alignment: Optional[str] = Field(pattern=r'^[lcr][tcb]$', default="lb", description="Two-letter alignment code: horizontal (l=left, c=center, r=right) and vertical (t=top, c=center, b=bottom).")


class DateWidgetModel(WidgetModel):
    widget_type: Literal["Date"] = "Date"
    date_format: _DateFormatField
    alignment: Optional[str] = Field(pattern=r'^[lcr][tcb]$', default="lb", description="Two-letter alignment code: horizontal (l=left, c=center, r=right) and vertical (t=top, c=center, b=bottom).")


class RoomCalendarWidgetModel(WidgetModel):
    widget_type: Literal["RoomCalendar"] = "RoomCalendar"
    date_format_long: _DateFormatField
    date_format: _DateFormatField
    time_format: _TimeFormatField
    room_number: str
    room_name: str
    ical_url: str


class WeatherWidgetModel(WidgetModel):
    """Shared fields for the Open-Meteo-backed weather widgets below."""
    latitude: float = Field(description="Latitude of the forecast location, e.g. 52.52.")
    longitude: float = Field(description="Longitude of the forecast location, e.g. 13.405.")


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

# discriminated union: widget_type selects the concrete model and a
# missing/unknown widget_type is a validation error instead of silently
# matching the first union member
AnyWidget = Annotated[
    Union[
        DateWidgetModel, TextWidgetModel, RoomCalendarWidgetModel,
        WeatherNowWidgetModel, WeatherForecastWidgetModel, WeatherChartWidgetModel,
    ],
    Field(discriminator="widget_type"),
]


class ScreenModel(BaseModel):
    # Tuple[int, int] -- see the same note on WidgetModel above.
    width: int = Field(description="Canvas width in pixels.")
    height: int = Field(description="Canvas height in pixels.")
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
