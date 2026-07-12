import datetime
from zoneinfo import ZoneInfo

from extensions.epaper.core.datasources.ical import _extract_events


ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//test//EN
BEGIN:VEVENT
UID:timed-1
DTSTART;TZID=Europe/Berlin:20260708T100000
DTEND;TZID=Europe/Berlin:20260708T113000
SUMMARY:Timed event
END:VEVENT
BEGIN:VEVENT
UID:allday-1
DTSTART;VALUE=DATE:20260709
DTEND;VALUE=DATE:20260711
SUMMARY:Two-day all-day event
END:VEVENT
END:VCALENDAR
"""

TZ = ZoneInfo("Europe/Berlin")
START = datetime.datetime(2026, 7, 7, tzinfo=TZ)
END = START + datetime.timedelta(days=30)


def test_timed_event_keeps_its_time():
    events = _extract_events(ICS, START, END, [], False)
    timed = next(e for e in events if e["summary"] == "Timed event")
    dtstart = datetime.datetime.fromisoformat(timed["dtstart"])
    dtend = datetime.datetime.fromisoformat(timed["dtend"])
    assert (dtstart.hour, dtstart.minute) == (10, 0)
    assert (dtend.hour, dtend.minute) == (11, 30)


def test_all_day_event_ends_at_2359_of_last_day():
    events = _extract_events(ICS, START, END, [], False)
    allday = next(e for e in events if e["summary"] == "Two-day all-day event")
    dtstart = datetime.datetime.fromisoformat(allday["dtstart"])
    dtend = datetime.datetime.fromisoformat(allday["dtend"])
    assert dtstart == datetime.datetime(2026, 7, 9, 0, 0, tzinfo=TZ)
    # DTEND 2026-07-11 is exclusive, so the event ends 2026-07-10 23:59
    assert dtend == datetime.datetime(2026, 7, 10, 23, 59, tzinfo=TZ)


def test_events_sorted_by_start():
    events = _extract_events(ICS, START, END, [], False)
    starts = [e["dtstart"] for e in events]
    assert starts == sorted(starts)


def test_organizer_extracted_from_summary():
    ics = ICS.replace("SUMMARY:Timed event", "SUMMARY:Maier Besprechung")
    events = _extract_events(ics, START, END, ["Maier", "Schulze"], True)
    timed = next(e for e in events if "Besprechung" in e["summary"])
    assert timed["organizer"] == "Maier"
    assert timed["summary"] == "Besprechung"
