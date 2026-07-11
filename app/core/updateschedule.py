import datetime
import json
import os
from zoneinfo import ZoneInfo
import aiofiles
from dateutil.rrule import rrule, DAILY, MO, TU, WE, TH, FR, SA, SU
from app.config import app_config
from app.util import logger
from app.models.updateschedulemodel import ALL_WEEKDAYS, UpdateScheduleModel


class UpdateSchedule:
    def __init__(self, id: str, config: UpdateScheduleModel, config_mtime: datetime.datetime):
        self.id = id
        self.config = config
        self.config_mtime = config_mtime


    def get_next_update(self, future_days=7) -> datetime.datetime:
        """
        Get the next update time for this schedule within the next future_days days.
        """
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))
        next_update = None

        for s in self.config.schedules:
            for t in s.times:
                # by_months/by_weekdays are never None (see WeeklyScheduleModel);
                # an empty list behaves the same as "all" in dateutil.rrule, not
                # "none", so no special-casing is needed here either way
                by_weekdays = [ALL_WEEKDAYS.index(wd) for wd in s.by_weekdays]

                for dt in rrule(freq=DAILY, dtstart=now, until=now + datetime.timedelta(days=future_days), bymonth=s.by_months, byweekday=by_weekdays):
                    dt = dt.replace(hour=int(t.time[:2]), minute=int(t.time[3:]), second=0, microsecond=0)
                    if dt > now and (not next_update or dt < next_update):
                        next_update = dt
                        break

        return next_update


async def get_schedule_by_id(schedule_id: str) -> UpdateSchedule:
    """
    Get a schedule instance by its id.
    """
    # load schedule model from file
    schedule_model_file = os.path.join(app_config.schedule_dir, f"{schedule_id}.json")
    try:
        async with aiofiles.open(schedule_model_file, 'r') as f:
            j = json.loads(await f.read())
        config = UpdateScheduleModel(**j)
        config_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(schedule_model_file), tz=ZoneInfo("UTC"))
    except Exception as e:
        logger.info(f"Error reading schedule model file {schedule_model_file}: {e}")
        return None

    return UpdateSchedule(schedule_id, config, config_mtime)

