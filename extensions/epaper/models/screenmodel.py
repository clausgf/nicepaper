import datetime
from typing import Annotated, List, Optional, Tuple, Union, Literal
from pydantic import BaseModel, Field

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
    widget_type: Literal["Text", "Date", "RoomCalendar"]

    # Tuple[int, int] fields (position/size) aren't renderable by niceview
    # (an unrecognised field type falls back to a plain ui.input bound to
    # a raw string -- wrong type), so position/size/font are flat scalar
    # fields here instead; `position`/`size`/`font` below are computed
    # properties for the drawing code, not part of the JSON schema.
    position_x: int = Field(description="Horizontal position in pixels from the left edge.")
    position_y: int = Field(description="Vertical position in pixels from the top edge.")
    size_width: Optional[int] = Field(default=None, description="Leave empty for automatic width.")
    size_height: Optional[int] = Field(default=None, description="Leave empty for automatic height.")
    init_background: Optional[bool] = True
    clipping: Optional[bool] = False
    font_name: Optional[str] = Field(default=None, description="Font file name. Leave empty to use the screen's default font.")
    font_size: Optional[int] = Field(default=None, description="Font size in points. Leave empty to use the screen's default font.")

    @property
    def position(self) -> Tuple[int, int]:
        return (self.position_x, self.position_y)

    @property
    def size(self) -> Optional[Tuple[int, int]]:
        if self.size_width is None or self.size_height is None:
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
        if self.font_name is None or self.font_size is None:
            return None
        return (self.font_name, self.font_size)


class TextWidgetModel(WidgetModel):
    widget_type: Literal["Text"] = "Text"
    text: str
    alignment: Optional[str] = Field(pattern=r'^[lcr][tcb]$', default="lb")


class DateWidgetModel(WidgetModel):
    widget_type: Literal["Date"] = "Date"
    date_format: _DateFormatField
    alignment: Optional[str] = Field(pattern=r'^[lcr][tcb]$', default="lb")


class RoomCalendarWidgetModel(WidgetModel):
    widget_type: Literal["RoomCalendar"] = "RoomCalendar"
    date_format_long: _DateFormatField
    date_format: _DateFormatField
    time_format: _TimeFormatField
    room_number: str
    room_name: str
    ical_url: str

# discriminated union: widget_type selects the concrete model and a
# missing/unknown widget_type is a validation error instead of silently
# matching the first union member
AnyWidget = Annotated[
    Union[DateWidgetModel, TextWidgetModel, RoomCalendarWidgetModel],
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
