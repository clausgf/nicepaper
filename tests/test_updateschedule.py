import datetime
from zoneinfo import ZoneInfo

from app.config import app_config
from app.core.updateschedule import UpdateSchedule
from app.models.updateschedulemodel import ALL_MONTHS, ALL_WEEKDAYS, TimeModel, UpdateScheduleModel, WeeklyScheduleModel


def test_weekly_schedule_defaults_to_all_months_and_weekdays():
    s = WeeklyScheduleModel(times=[TimeModel(time="06:00")])
    assert s.by_months == ALL_MONTHS
    assert s.by_weekdays == ALL_WEEKDAYS


def test_get_next_update_unconstrained_finds_a_time_within_a_day():
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    soon = (now + datetime.timedelta(minutes=2)).strftime("%H:%M")
    config = UpdateScheduleModel(name="t", schedules=[
        WeeklyScheduleModel(times=[TimeModel(time=soon)]),
    ])
    schedule = UpdateSchedule("t", config, now)

    next_update = schedule.get_next_update()

    assert next_update is not None
    assert next_update > now
    assert next_update - now < datetime.timedelta(days=1, minutes=5)


def test_get_next_update_respects_weekday_restriction():
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    other_weekday = ALL_WEEKDAYS[(now.weekday() + 1) % 7]
    config = UpdateScheduleModel(name="t", schedules=[
        WeeklyScheduleModel(by_weekdays=[other_weekday], times=[TimeModel(time="00:01")]),
    ])
    schedule = UpdateSchedule("t", config, now)

    next_update = schedule.get_next_update()

    assert next_update is not None
    assert ALL_WEEKDAYS[next_update.weekday()] == other_weekday
