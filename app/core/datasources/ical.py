import asyncio
import datetime
import json
import os
from zoneinfo import ZoneInfo
import aiofiles
import aiohttp
from icalendar import Calendar
import recurring_ical_events
from app.config import app_config
from app.util import logger


_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    """
    Create the shared HTTP session lazily: a ClientSession must be
    created inside a running event loop.
    """
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(raise_for_status=True)
    return _session


def _extract_events(ical_text: str, start_date: datetime.datetime, end_date: datetime.datetime,
                    organizer_names: list, extract_organizer_from_summary: bool) -> list:
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
        if app_config.ical_max_days > 0 and dtstart > end_date:
            continue
        if organizer is None and extract_organizer_from_summary and len(organizer_names) > 0:
            contained = [name for name in organizer_names if summary.startswith(name)]
            if contained:
                summary = summary.replace(contained[0], "")
                organizer = contained[0]

        result.append({
            "dtstart": dtstart.isoformat(),
            "dtend": dtend.isoformat(),
            "organizer": str(organizer).strip() if organizer else "",
            "summary": summary.strip()
        })

    result.sort(key=lambda e: datetime.datetime.fromisoformat(e.get("dtstart")))
    return result


async def get_from_ical(id: str, url: str, extract_organizer_from_summary: bool = True):
    # load data from cache
    data = None
    cache_filename = os.path.join(app_config.ical_dir, f"{id}.json")
    if os.path.exists(cache_filename):
        async with aiofiles.open(cache_filename, "r") as cache_file:
            data = json.loads(await cache_file.read())
        logger.debug(f"{id} loaded {len(data.get('events', []))} events from cache")
    if data is not None and 'last_update' in data and 'events' in data:
        last_update = datetime.datetime.fromisoformat(data['last_update'])
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))
        timedelta = now - last_update
        if timedelta.total_seconds() < app_config.ical_update_interval_s:
            logger.info(f"Ical {id} skipping update, last update was {timedelta.total_seconds()} seconds ago")
            return data['events']

    # refresh data from ical feed
    logger.info(f"Ical {id} updating from {url}")
    async with _get_session().get(url) as response:
        response_text = await response.text()
        logger.info(f"Ical {id} response status: {response.status}")

    start_date = datetime.datetime.now(ZoneInfo(app_config.timezone))
    end_date = start_date + datetime.timedelta(days=app_config.ical_max_days)

    organizer_names = []
    if app_config.organizer_names_file and extract_organizer_from_summary:
        async with aiofiles.open(app_config.organizer_names_file, "r") as org_file:
            organizer_names = json.loads(await org_file.read())

    events = await asyncio.to_thread(
        _extract_events, response_text, start_date, end_date,
        organizer_names, extract_organizer_from_summary)

    data = {
        'last_update': start_date.isoformat(),
        'events': events
    }
    async with aiofiles.open(cache_filename, "w") as cache_file:
        await cache_file.write(json.dumps(data))

    logger.debug(f"{id} collected {len(events)} events")
    return events
