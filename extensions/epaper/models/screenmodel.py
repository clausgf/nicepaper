import datetime
from typing import Annotated, List, Optional, Tuple, Union, Literal
from pydantic import BaseModel, Field
from niceview.fieldinfo import FieldInfo

# Baked-in UI styling: niceview reads FieldInfo instances out of Annotated
# metadata to decide how to render a field. Kept here at the model layer
# (rather than repeated at every render_field()/render() call site) so
# every form over these models -- standalone, nice4iot extension, or a
# future consumer -- gets the same compact styling automatically. Sharing
# one instance across fields is safe: niceview's field resolver copies it
# before merging in any overrides, it never mutates the shared instance.
_DENSE_INPUT = FieldInfo(props='outline dense')
_DENSE_TOGGLE = FieldInfo(props='dense')
_DENSE_SELECT = FieldInfo(props='outline dense', widget_type='ui.select')

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
    position_x: Annotated[int, Field(description="Horizontal position in pixels from the left edge."), _DENSE_INPUT]
    position_y: Annotated[int, Field(description="Vertical position in pixels from the top edge."), _DENSE_INPUT]
    size_width: Annotated[Optional[int], Field(default=None, description="Leave empty for automatic width."), _DENSE_INPUT]
    size_height: Annotated[Optional[int], Field(default=None, description="Leave empty for automatic height."), _DENSE_INPUT]
    init_background: Annotated[Optional[bool], Field(default=True), _DENSE_TOGGLE]
    clipping: Annotated[Optional[bool], Field(default=False), _DENSE_TOGGLE]
    font_name: Annotated[Optional[str], Field(default=None, description="Font file name. Leave empty to use the screen's default font."), _DENSE_SELECT]
    font_size: Annotated[Optional[int], Field(default=None, description="Font size in points. Leave empty to use the screen's default font."), _DENSE_INPUT]

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
    text: Annotated[str, Field(), _DENSE_INPUT]
    alignment: Annotated[Optional[str], Field(pattern=r'^[lcr][tcb]$', default="lb"), _DENSE_INPUT]


class DateWidgetModel(WidgetModel):
    widget_type: Literal["Date"] = "Date"
    date_format: _DateFormatField
    alignment: Annotated[Optional[str], Field(pattern=r'^[lcr][tcb]$', default="lb"), _DENSE_INPUT]


class RoomCalendarWidgetModel(WidgetModel):
    widget_type: Literal["RoomCalendar"] = "RoomCalendar"
    date_format_long: _DateFormatField
    date_format: _DateFormatField
    time_format: _TimeFormatField
    room_number: Annotated[str, Field(), _DENSE_INPUT]
    room_name: Annotated[str, Field(), _DENSE_INPUT]
    ical_url: Annotated[str, Field(), _DENSE_INPUT]

# discriminated union: widget_type selects the concrete model and a
# missing/unknown widget_type is a validation error instead of silently
# matching the first union member
AnyWidget = Annotated[
    Union[DateWidgetModel, TextWidgetModel, RoomCalendarWidgetModel],
    Field(discriminator="widget_type"),
]


class ScreenModel(BaseModel):
    # Tuple[int, int] -- see the same note on WidgetModel above.
    width: Annotated[int, Field(description="Canvas width in pixels."), _DENSE_INPUT]
    height: Annotated[int, Field(description="Canvas height in pixels."), _DENSE_INPUT]
    update_schedule_id: Annotated[
        Optional[str],
        Field(
            default="default",
            description=(
                "Name of a schedule file (without .json) that determines when "
                "this screen expires and is re-rendered. Leave empty to only "
                "re-render on request or when a widget provides its own "
                "expiry (e.g. RoomCalendar's next event)."
            ),
        ),
        _DENSE_INPUT,
    ]
    widgets: List[AnyWidget] = []

    @property
    def size(self) -> Tuple[int, int]:
        return (self.width, self.height)
