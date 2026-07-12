import asyncio
import datetime
import json
import uuid
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from extensions.epaper.config import app_config
from extensions.epaper.core.updateschedule import UpdateSchedule, get_schedule_by_id
from extensions.epaper.models.updateschedulemodel import ALL_MONTHS, ALL_WEEKDAYS, WeeklyScheduleModel
from extensions.epaper.paths import EpaperPaths


def test_weekly_schedule_defaults_to_all_months_and_weekdays():
    s = WeeklyScheduleModel(times=["06:00"])
    assert s.by_months == ALL_MONTHS
    assert s.by_weekdays == ALL_WEEKDAYS


def test_weekly_schedule_rejects_invalid_time():
    with pytest.raises(ValidationError):
        WeeklyScheduleModel(times=["25:99"])


def test_weekly_schedule_sorts_times():
    s = WeeklyScheduleModel(times=["18:00", "06:00", "12:00"])
    assert s.times == ["06:00", "12:00", "18:00"]


def test_get_next_update_unconstrained_finds_a_time_within_a_day():
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    soon = (now + datetime.timedelta(minutes=2)).strftime("%H:%M")
    schedules = [WeeklyScheduleModel(times=[soon])]
    schedule = UpdateSchedule("t", schedules, now)

    next_update = schedule.get_next_update()

    assert next_update is not None
    assert next_update > now
    assert next_update - now < datetime.timedelta(days=1, minutes=5)


def test_get_next_update_respects_weekday_restriction():
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    other_weekday = ALL_WEEKDAYS[(now.weekday() + 1) % 7]
    schedules = [WeeklyScheduleModel(by_weekdays=[other_weekday], times=["00:01"])]
    schedule = UpdateSchedule("t", schedules, now)

    next_update = schedule.get_next_update()

    assert next_update is not None
    assert ALL_WEEKDAYS[next_update.weekday()] == other_weekday


def test_get_schedule_by_id_reads_plain_list_file(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    schedule_id = f"schedtest-{uuid.uuid4().hex[:8]}"
    schedule_file = paths.schedule_dir / f"{schedule_id}.json"
    with open(schedule_file, "w") as f:
        json.dump([
            {"type": "weekly", "by_weekdays": ["Mon"], "times": ["06:00"]},
        ], f)

    schedule = asyncio.run(get_schedule_by_id(paths, schedule_id))
    assert schedule is not None
    assert len(schedule.schedules) == 1
    assert schedule.schedules[0].by_weekdays == ["Mon"]
    assert schedule.schedules[0].by_months == ALL_MONTHS


def test_get_schedule_by_id_returns_none_for_missing_file(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    assert asyncio.run(get_schedule_by_id(paths, "does-not-exist")) is None
