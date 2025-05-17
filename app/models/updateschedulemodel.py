from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class TimeModel(BaseModel):
    time: str = Field(None, pattern=r'^\d{2}:\d{2}$', description="Time in format 'hh:mm'")

class WeeklyScheduleModel(BaseModel):
    type: Literal["weekly"] = "weekly"
    by_months: Optional[List[int]] = None
    by_weekdays: Optional[List[Literal["MO", "TU", "WE", "TH", "FR", "SA", "SU"]]] = None
    times: List[TimeModel] = Field(None, description="List of times an update is scheduled")

class UpdateScheduleModel(BaseModel):
    name: str
    schedules: List[WeeklyScheduleModel]
