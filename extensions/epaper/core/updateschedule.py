import datetime
import json
import os
from typing import List
from zoneinfo import ZoneInfo
import aiofiles
import pydantic
from dateutil.rrule import rrule, DAILY
from extensions.epaper.config import app_config
from extensions.epaper.util import logger
from extensions.epaper.models.updateschedulemodel import ALL_WEEKDAYS, WeeklyScheduleModel
from extensions.epaper.paths import EpaperPaths

_schedules_adapter = pydantic.TypeAdapter(List[WeeklyScheduleModel])


class UpdateSchedule:
    def __init__(self, id: str, schedules: List[WeeklyScheduleModel], config_mtime: datetime.datetime):
        self.id = id
        self.schedules = schedules
        self.config_mtime = config_mtime


    def get_next_update(self, future_days=7) -> datetime.datetime:
        """
        Get the next update time for this schedule within the next future_days days.
        """
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))
        next_update = None

        for s in self.schedules:
            for t in s.times:
                # by_months/by_weekdays are never None (see WeeklyScheduleModel);
                # an empty list behaves the same as "all" in dateutil.rrule, not
                # "none", so no special-casing is needed here either way
                by_weekdays = [ALL_WEEKDAYS.index(wd) for wd in s.by_weekdays]

                for dt in rrule(freq=DAILY, dtstart=now, until=now + datetime.timedelta(days=future_days), bymonth=s.by_months, byweekday=by_weekdays):
                    dt = dt.replace(hour=int(t[:2]), minute=int(t[3:]), second=0, microsecond=0)
                    if dt > now and (not next_update or dt < next_update):
                        next_update = dt
                        break

        return next_update


async def get_schedule_by_id(paths: EpaperPaths, schedule_id: str) -> UpdateSchedule:
    """
    Get a schedule instance by its id, or None. The schedule file is a plain
    JSON list of weekly schedule rules (List[WeeklyScheduleModel]).

    An empty/None schedule_id means the screen intentionally has no update
    schedule (see ScreenModel.update_schedule_id) -- that is not an error and
    is returned silently. A non-empty id whose file is missing or invalid is a
    dangling reference: the screen still renders but won't be re-rendered on a
    schedule, so it is logged as a warning (see also the editor, which flags
    such references inline and in the screen list).
    """
    if not schedule_id:
        return None

    schedule_model_file = paths.schedule_dir / f"{schedule_id}.json"
    if not schedule_model_file.is_file():
        logger.warning(
            f"Update schedule '{schedule_id}' is referenced but {schedule_model_file} is missing; "
            f"the screen will not be re-rendered on a schedule.")
        return None
    try:
        async with aiofiles.open(schedule_model_file, 'r') as f:
            j = json.loads(await f.read())
        schedules = _schedules_adapter.validate_python(j)
        config_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(schedule_model_file), tz=ZoneInfo("UTC"))
    except Exception as e:
        logger.warning(f"Update schedule '{schedule_id}' file {schedule_model_file} is invalid: {e}")
        return None

    return UpdateSchedule(schedule_id, schedules, config_mtime)

