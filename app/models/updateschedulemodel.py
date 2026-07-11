from typing import Annotated, List, Literal
from pydantic import BaseModel, Field, field_validator

ALL_MONTHS = list(range(1, 13))
# Monday-first, matching dateutil.rrule's byweekday numbering (MO=0) and
# datetime.date.weekday() -- ALL_WEEKDAYS.index(wd) in updateschedule.py
# relies on this order, not on the label text itself
ALL_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TIME_PATTERN = r'^([01]\d|2[0-3]):[0-5]\d$'


class WeeklyScheduleModel(BaseModel):
    type: Literal["weekly"] = "weekly"
    # not Optional: a UI multiselect can only show "empty" or "populated",
    # not a separate "unset" state, so "no restriction" is expressed as
    # every value being selected by default rather than as None
    by_months: List[Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]] = Field(default_factory=lambda: list(ALL_MONTHS))
    by_weekdays: List[Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]] = Field(default_factory=lambda: list(ALL_WEEKDAYS))
    # plain list[str] with a per-item pattern constraint, not a wrapper model:
    # renders as ui.input_chips (list[str]'s default niceview widget), with the
    # HH:MM pattern still enforced by pydantic on each chip
    times: List[Annotated[str, Field(pattern=TIME_PATTERN)]] = Field(
        description="List of times an update is scheduled, each in 'hh:mm' format")

    @field_validator('times')
    @classmethod
    def _sort_times(cls, value: List[str]) -> List[str]:
        # sort on every validation (not just at the UI layer) so the list is
        # sorted regardless of entry order or access path (chips autosave,
        # file load, raw API); zero-padded HH:MM sorts correctly as strings
        return sorted(value)
