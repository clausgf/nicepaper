import datetime
from typing import List, Optional, Tuple, Union, Literal
from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    last_update_at: datetime.datetime
    expires_at: datetime.datetime
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

AnyWidget = Union[DateWidgetModel, TextWidgetModel, RoomCalendarWidgetModel]


class ScreenModel(BaseModel):
    size: Tuple[int, int]
    update_schedule_id: Optional[str] = "default"
    widgets: List[AnyWidget] = []
