from typing import List, Literal
from pydantic import BaseModel, Field

ALL_MONTHS = list(range(1, 13))
ALL_WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


class TimeModel(BaseModel):
    time: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$', description="Time in format 'hh:mm'")

class WeeklyScheduleModel(BaseModel):
    type: Literal["weekly"] = "weekly"
    # not Optional: a UI multiselect can only show "empty" or "populated",
    # not a separate "unset" state, so "no restriction" is expressed as
    # every value being selected by default rather than as None
    by_months: List[Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]] = Field(default_factory=lambda: list(ALL_MONTHS))
    by_weekdays: List[Literal["MO", "TU", "WE", "TH", "FR", "SA", "SU"]] = Field(default_factory=lambda: list(ALL_WEEKDAYS))
    times: List[TimeModel] = Field(description="List of times an update is scheduled")
