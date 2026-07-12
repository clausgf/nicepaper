import datetime
from typing import Annotated, List, Optional, Tuple, Union, Literal
from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    last_update_at: datetime.datetime
    # expires_at is None when neither an update schedule nor a widget
    # provides a next update time
    expires_at: Optional[datetime.datetime] = None
    version: str


class WidgetModel(BaseModel):
    widget_type: Literal["Text", "Date", "RoomCalendar"]
    position: Tuple[int, int]
    size: Optional[Tuple[int, int]] = None
    init_background: Optional[bool] = True
    clipping: Optional[bool] = False
    font: Optional[Tuple[str, int]] = None


class TextWidgetModel(WidgetModel):
    widget_type: Literal["Text"] = "Text"
    text: str
    alignment: Optional[str] = Field(pattern=r'^[lcr][tcb]$', default="lb")


class DateWidgetModel(WidgetModel):
    widget_type: Literal["Date"] = "Date"
    date_format: Optional[str] = None
    alignment: Optional[str] = Field(pattern=r'^[lcr][tcb]$', default="lb")


class RoomCalendarWidgetModel(WidgetModel):
    widget_type: Literal["RoomCalendar"] = "RoomCalendar"
    date_format_long: Optional[str] = None
    date_format: Optional[str] = None
    time_format: Optional[str] = None
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
    size: Tuple[int, int]
    update_schedule_id: Optional[str] = "default"
    widgets: List[AnyWidget] = []
