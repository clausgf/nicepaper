import asyncio
import datetime
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo
import aiofiles
import aiohttp
from icalendar import Calendar
import recurring_ical_events
from extensions.epaper.global_config.backend import app_config
from extensions.epaper.util import logger


_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    """
    Create the shared HTTP session lazily: a ClientSession must be
    created inside a running event loop.
    """
    global _session
    if _session is None or _session.closed:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0"}
        _session = aiohttp.ClientSession(raise_for_status=True, headers=headers)
    return _session


def _extract_events(ical_text: str, start_date: datetime.datetime, end_date: datetime.datetime,
                    organizer_names: list, extract_organizer_from_summary: bool, max_days: int,
                    feed_id: str = "") -> list:
    """
    Parse an iCal feed and extract the events between start_date and end_date
    as serializable dicts, sorted by start time. CPU bound, intended to run
    in a worker thread.
    """
    tzinfo = ZoneInfo(app_config.timezone)
    result = []

    cal = Calendar.from_ical(ical_text)
    events = recurring_ical_events.of(cal).between(start_date, end_date)
    for event in events:
        logger.debug(event)
        dtstart_prop = event.get('DTSTART')
        dtend_prop = event.get('DTEND')
        organizer = event.get('ORGANIZER')
        summary = event.get('SUMMARY')
        categories = event.get('CATEGORIES','') # categories is an optional, comma-separated list of strings
        if dtstart_prop is None or dtend_prop is None or summary is None:
            continue
        dtstart = dtstart_prop.dt
        dtend = dtend_prop.dt

        # all-day events carry dates instead of datetimes (note that a
        # datetime is also a date, hence the second isinstance check):
        # they start at 00:00 and, since an all-day DTEND is exclusive,
        # end at 23:59 of the day before DTEND
        if isinstance(dtstart, datetime.date) and not isinstance(dtstart, datetime.datetime):
            dtstart = datetime.datetime.combine(dtstart, datetime.time(0, 0, 0, tzinfo=tzinfo))
        if isinstance(dtend, datetime.date) and not isinstance(dtend, datetime.datetime):
            last_day = dtend - datetime.timedelta(days=1)
            if last_day < dtstart.date():
                last_day = dtstart.date()
            dtend = datetime.datetime.combine(last_day, datetime.time(23, 59, 0, tzinfo=tzinfo))

        # treat naive (floating) times as local times
        if dtstart.tzinfo is None:
            dtstart = dtstart.replace(tzinfo=tzinfo)
        if dtend.tzinfo is None:
            dtend = dtend.replace(tzinfo=tzinfo)

        if dtend < start_date:
            continue
        if max_days > 0 and dtstart > end_date:
            continue
        if organizer is not None:
            if extract_organizer_from_summary and organizer_names:
                logger.info(f"Ical {feed_id}: event {summary!r} already has ORGANIZER {str(organizer)!r} "
                           "-- organizer-name extraction skipped")
        elif extract_organizer_from_summary and organizer_names:
            contained = [name for name in organizer_names if summary.startswith(name)]
            if contained:
                summary = summary.replace(contained[0], "")
                organizer = contained[0]
                logger.info(f"Ical {feed_id}: matched organizer name {organizer!r} in summary")
            else:
                logger.info(f"Ical {feed_id}: no organizer name matched summary {summary!r} "
                           f"(candidates: {organizer_names})")

        result.append({
            "dtstart": dtstart.isoformat(),
            "dtend": dtend.isoformat(),
            "organizer": str(organizer).strip() if organizer else "",
            "summary": summary.strip(),
            "categories": categories.strip(),
        })

    result.sort(key=lambda e: datetime.datetime.fromisoformat(e["dtstart"]))
    return result


@dataclass
class IcalStatus:
    """Outcome of an iCal fetch for one feed, for both the caller (events +
    staleness) and the dashboard health view (failing/error/retry). Mirrors
    WeatherStatus/EntityStatus (weather.py/homeassistant.py)."""
    id: str
    events: Optional[list]                            # last-known events; None if never fetched
    last_update: Optional[datetime.datetime]          # last successful fetch
    fresh: bool                                       # last_update within the update interval
    failing: bool                                     # last attempt failed / currently backing off
    fail_count: int                                   # consecutive failures
    retry_after: Optional[datetime.datetime]          # earliest next network attempt
    error: Optional[str]                              # last error message (dashboard tooltip)


def _cache_filename(ical_dir: Path, id: str) -> Path:
    return Path(ical_dir) / f"{id}.json"


def _read_cache(cache_filename: Path) -> dict:
    try:
        with open(cache_filename, "r") as f:
            cache = json.load(f)
        return cache if isinstance(cache, dict) else {}
    except Exception:
        return {}


def _parse_dt(value: Optional[str]) -> Optional[datetime.datetime]:
    return datetime.datetime.fromisoformat(value) if value else None


def _status_from_cache(id: str, cache: dict, now: datetime.datetime,
                       update_interval_s: Optional[int] = None) -> IcalStatus:
    last_update = _parse_dt(cache.get('last_update'))
    fresh = (last_update is not None and update_interval_s is not None
             and (now - last_update).total_seconds() < update_interval_s)
    fail_count = int(cache.get('fail_count', 0))
    return IcalStatus(
        id=cache.get('id', id), events=cache.get('events'),
        last_update=last_update, fresh=fresh, failing=fail_count > 0, fail_count=fail_count,
        retry_after=_parse_dt(cache.get('retry_after')), error=cache.get('error'),
    )


def _backoff_seconds(fail_count: int) -> float:
    """Exponential backoff (base doubling per consecutive failure), capped."""
    base = max(1, app_config.ical_retry_min_s)
    return float(min(base * (2 ** max(0, fail_count - 1)), app_config.ical_retry_max_s))


def read_all_ical_statuses(ical_dir: Path) -> list[IcalStatus]:
    """Status of every cached feed (no fetch), for the dashboard health view.
    `update_interval_s` isn't known here (it's the caller's own config, see
    get_from_ical()'s docstring), so `fresh` stays False -- the dashboard
    only reads `.failing` (see ui/cards.py's _datasource_row)."""
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    statuses = []
    for path in sorted(Path(ical_dir).glob("*.json")):
        cache = _read_cache(path)
        if not cache.get('id'):
            continue
        statuses.append(_status_from_cache(cache['id'], cache, now))
    return statuses


async def get_from_ical(ical_dir: Path, organizer_names_file: Optional[Path], id: str, url: str,
                        update_interval_s: int, max_days: int,
                        username: str = "", password: str = "", headers: Optional[dict] = None,
                        extract_organizer_from_summary: bool = True) -> IcalStatus:
    """
    Fetch (or return cached) events from an iCal feed, as an IcalStatus.
    `id` names the cache file. update_interval_s/max_days are the caller's
    own config, not read from anywhere here: RoomCalendar passes its room's
    BookingSystemModel's update_interval/max_days_ahead (room/backend.py's
    get_room_events). username/password (HTTP Basic Auth) and headers are
    optional, both from a BookingSystemModel when the feed needs them.

    Never raises: on a fetch/parse failure it records the failure (fail_count,
    exponential backoff via retry_after, last error) in the same cache file
    and returns the last-known events with failing=True (graceful
    degradation, matching the weather/Home Assistant datasources -- iCal used
    to have neither, so a broken feed was retried on every single render).
    get_room_events() (room/backend.py) adapts this back to the
    raise-on-total-failure contract its own callers already expect.
    """
    cache_filename = _cache_filename(ical_dir, id)
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    cache = _read_cache(cache_filename)
    status = _status_from_cache(id, cache, now, update_interval_s)

    if status.fresh:
        logger.info(f"Ical {id} skipping update, cached data is fresh")
        return status
    if status.retry_after is not None and now < status.retry_after:
        logger.info(f"Ical {id} backing off until {status.retry_after.isoformat()}")
        return status

    logger.info(f"Ical {id} updating from {url}")
    request_headers = dict(headers) if headers else {}
    if username:
        request_headers['Authorization'] = aiohttp.encode_basic_auth(username, password)
    try:
        async with _get_session().get(url, headers=request_headers or None) as response:
            response_text = await response.text()
            logger.info(f"Ical {id} response status: {response.status}")

        start_date = now
        end_date = start_date + datetime.timedelta(days=max_days)

        organizer_names = []
        if organizer_names_file and os.path.exists(organizer_names_file) and extract_organizer_from_summary:
            async with aiofiles.open(organizer_names_file, "r") as org_file:
                organizer_names = json.loads(await org_file.read())
        logger.info(f"Ical {id}: {len(organizer_names)} organizer name(s) loaded for summary extraction: "
                   f"{organizer_names}")

        events = await asyncio.to_thread(
            _extract_events, response_text, start_date, end_date,
            organizer_names, extract_organizer_from_summary, max_days, id)
    except Exception as e:
        fail_count = status.fail_count + 1
        retry_after = now + datetime.timedelta(seconds=_backoff_seconds(fail_count))
        logger.error(f"Error occurred while fetching ical data for {id} from {url}: {e}; "
                     f"retrying after {retry_after.isoformat()} (attempt {fail_count})")
        cache.update(id=id, fail_count=fail_count, retry_after=retry_after.isoformat(), error=str(e))
        async with aiofiles.open(cache_filename, "w") as cache_file:
            await cache_file.write(json.dumps(cache))
        return _status_from_cache(id, cache, now, update_interval_s)

    cache = {'id': id, 'last_update': now.isoformat(), 'events': events}  # success clears fail/backoff state
    async with aiofiles.open(cache_filename, "w") as cache_file:
        await cache_file.write(json.dumps(cache))

    logger.debug(f"{id} collected {len(events)} events")
    return _status_from_cache(id, cache, now, update_interval_s)
