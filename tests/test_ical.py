import asyncio
import datetime
import json
from zoneinfo import ZoneInfo

import aiohttp

from extensions.epaper.global_config.backend import app_config
from extensions.epaper.core.datasources.ical import _extract_events, get_from_ical, read_all_ical_statuses


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
    events = _extract_events(ICS, START, END, [], False, 30)
    timed = next(e for e in events if e["summary"] == "Timed event")
    dtstart = datetime.datetime.fromisoformat(timed["dtstart"])
    dtend = datetime.datetime.fromisoformat(timed["dtend"])
    assert (dtstart.hour, dtstart.minute) == (10, 0)
    assert (dtend.hour, dtend.minute) == (11, 30)


def test_all_day_event_ends_at_2359_of_last_day():
    events = _extract_events(ICS, START, END, [], False, 30)
    allday = next(e for e in events if e["summary"] == "Two-day all-day event")
    dtstart = datetime.datetime.fromisoformat(allday["dtstart"])
    dtend = datetime.datetime.fromisoformat(allday["dtend"])
    assert dtstart == datetime.datetime(2026, 7, 9, 0, 0, tzinfo=TZ)
    # DTEND 2026-07-11 is exclusive, so the event ends 2026-07-10 23:59
    assert dtend == datetime.datetime(2026, 7, 10, 23, 59, tzinfo=TZ)


def test_events_sorted_by_start():
    events = _extract_events(ICS, START, END, [], False, 30)
    starts = [e["dtstart"] for e in events]
    assert starts == sorted(starts)


def test_organizer_extracted_from_summary():
    ics = ICS.replace("SUMMARY:Timed event", "SUMMARY:Maier Besprechung")
    events = _extract_events(ics, START, END, ["Maier", "Schulze"], True, 30)
    timed = next(e for e in events if "Besprechung" in e["summary"])
    assert timed["organizer"] == "Maier"
    assert timed["summary"] == "Besprechung"


def test_get_from_ical_uses_cache_within_update_interval(tmp_path):
    now = datetime.datetime.now(ZoneInfo("Europe/Berlin"))
    (tmp_path / "room-x.json").write_text(json.dumps({
        "id": "room-x", "last_update": now.isoformat(), "events": [{"summary": "cached"}],
    }))
    status = asyncio.run(get_from_ical(tmp_path, None, "room-x", "https://example.com/cal.ics",
                                       update_interval_s=600, max_days=30))
    assert status.events == [{"summary": "cached"}]
    assert status.fresh and not status.failing


class _FakeIcalResponse:
    def __init__(self, text):
        self._text = text
        self.status = 200
    async def __aenter__(self):
        return self
    async def __aexit__(self, *a):
        return False
    async def text(self):
        return self._text


class _FakeIcalSession:
    def __init__(self, text, captured):
        self._text = text
        self._captured = captured
    def get(self, url, headers=None):
        self._captured.update(url=url, headers=headers)
        return _FakeIcalResponse(self._text)


def test_get_from_ical_passes_auth_and_headers_to_the_request(tmp_path, monkeypatch):
    """A booking system's username/password/header (room/backend.py's
    get_room_events) must actually reach the HTTP request -- this is the
    'ical datasource compatible with the booking system config' part."""
    captured: dict = {}
    monkeypatch.setattr("extensions.epaper.core.datasources.ical._get_session",
                        lambda: _FakeIcalSession(ICS, captured))
    # the fixture's fixed 2026-07 dates are incidental here (this test is
    # about request wiring, not event parsing -- that's covered above), so
    # don't assert on how many of them still lie in get_from_ical's own
    # datetime.now()-based window
    asyncio.run(get_from_ical(tmp_path, None, "room-x", "https://example.com/cal.ics",
                              update_interval_s=600, max_days=30,
                              username="alice", password="secret",
                              headers={"X-Test": "1"}))
    assert captured["url"] == "https://example.com/cal.ics"
    assert captured["headers"]["X-Test"] == "1"
    assert captured["headers"]["Authorization"] == aiohttp.encode_basic_auth("alice", "secret")


def test_get_from_ical_omits_auth_without_username(tmp_path, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr("extensions.epaper.core.datasources.ical._get_session",
                        lambda: _FakeIcalSession(ICS, captured))
    asyncio.run(get_from_ical(tmp_path, None, "room-y", "https://example.com/cal.ics",
                              update_interval_s=600, max_days=30))
    assert captured["headers"] is None


class _FailingIcalResponse:
    async def __aenter__(self):
        raise RuntimeError("Cannot connect to host")
    async def __aexit__(self, *a):
        return False


class _FailingIcalSession:
    def get(self, url, headers=None):
        return _FailingIcalResponse()


def _fail_if_called():
    raise AssertionError("network must not be used here")


def test_get_from_ical_backs_off_and_degrades_gracefully(tmp_path, monkeypatch):
    """A failing feed keeps returning the last-known events (graceful
    degradation, matching weather/Home Assistant) and backs off instead of
    being re-fetched on every render."""
    monkeypatch.setattr(app_config, "ical_retry_min_s", 60)
    monkeypatch.setattr(app_config, "ical_retry_max_s", 1800)
    old = datetime.datetime.now(ZoneInfo("Europe/Berlin")) - datetime.timedelta(hours=2)
    (tmp_path / "room-x.json").write_text(json.dumps({
        "id": "room-x", "last_update": old.isoformat(), "events": [{"summary": "stale"}],
    }))
    monkeypatch.setattr("extensions.epaper.core.datasources.ical._get_session",
                        lambda: _FailingIcalSession())

    first = asyncio.run(get_from_ical(tmp_path, None, "room-x", "https://example.com/cal.ics",
                                      update_interval_s=600, max_days=30))
    assert first.events == [{"summary": "stale"}]
    assert first.failing and first.fail_count == 1 and first.retry_after is not None

    # inside the backoff window -> no request at all
    monkeypatch.setattr("extensions.epaper.core.datasources.ical._get_session", _fail_if_called)
    second = asyncio.run(get_from_ical(tmp_path, None, "room-x", "https://example.com/cal.ics",
                                       update_interval_s=600, max_days=30))
    assert second.events == [{"summary": "stale"}] and second.failing


def test_get_from_ical_never_fetched_returns_no_events(tmp_path, monkeypatch):
    monkeypatch.setattr("extensions.epaper.core.datasources.ical._get_session",
                        lambda: _FailingIcalSession())
    status = asyncio.run(get_from_ical(tmp_path, None, "room-y", "https://example.com/cal.ics",
                                       update_interval_s=600, max_days=30))
    assert status.events is None and status.failing


def test_read_all_ical_statuses(tmp_path):
    now = datetime.datetime.now(ZoneInfo("Europe/Berlin"))
    (tmp_path / "room-a.json").write_text(json.dumps({
        "id": "room-a", "last_update": now.isoformat(), "events": [],
    }))
    (tmp_path / "room-b.json").write_text(json.dumps({
        "id": "room-b", "fail_count": 2, "error": "timeout",
        "retry_after": (now + datetime.timedelta(minutes=5)).isoformat(),
    }))
    statuses = {s.id: s for s in read_all_ical_statuses(tmp_path)}
    assert statuses["room-a"].failing is False
    assert statuses["room-b"].failing and statuses["room-b"].fail_count == 2
    assert statuses["room-b"].events is None
