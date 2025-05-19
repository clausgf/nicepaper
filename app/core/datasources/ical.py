import datetime
import json
import os
from zoneinfo import ZoneInfo
import aiohttp
from icalendar import Calendar
import recurring_ical_events
from app.config import app_config
from app.util import logger


session = aiohttp.ClientSession(raise_for_status=True)


async def get_from_ical(id: str, url: str, extract_organizer_from_summary: bool = True):
    # load data from cache
    data = None
    cache_filename = os.path.join(app_config.ical_dir, f"{id}.json")
    if os.path.exists(cache_filename):
        with open(cache_filename, "r") as cache_file:
            data = json.load(cache_file)
            logger.debug(f"{id} loaded {len(data)} events from cache")
    if data is not None and 'last_update' in data and 'events' in data:
        last_update = datetime.datetime.fromisoformat(data['last_update'])
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))
        timedelta = now - last_update
        if timedelta.total_seconds() < app_config.ical_update_interval_s:
            logger.info(f"Ical {id} skipping update, last update was {timedelta.total_seconds()} seconds ago")
            return data['events']

    # refresh data from ical feed
    logger.info(f"Ical {id} updating from {url}")
    data = {
        'last_update': datetime.datetime.now(ZoneInfo(app_config.timezone)).isoformat(),
        'events': []
    }
    async with session.get(url) as response:
        response_text = await response.text()
        response_status = response.status
        logger.info(f"Ical {id} response status: {response_status}")

        start_date = datetime.datetime.now(ZoneInfo(app_config.timezone))
        timedelta = datetime.timedelta(days=app_config.ical_max_days)
        end_date = start_date + timedelta

        organizer_names = []
        if app_config.organizer_names_file and extract_organizer_from_summary:
            with open(app_config.organizer_names_file, "r") as org_file:
                organizer_names = json.load(org_file)

        cal = Calendar.from_ical(response_text)
        # for component in cal.walk():
        #     if component.name == "VEVENT":
        events = recurring_ical_events.of(cal).between(start_date, end_date)
        for event in events:
            dtstart = event.get('DTSTART').dt
            dtend = event.get('DTEND').dt
            organizer = event.get('ORGANIZER')
            summary = event.get('SUMMARY')
            if dtstart is None or dtend is None or summary is None:
                continue
            if dtend < start_date:
                continue
            if app_config.ical_max_days > 0 and dtstart > end_date:
                continue
            if organizer is None and extract_organizer_from_summary and len(organizer_names) > 0:
                contained = [name for name in organizer_names if summary.startswith(name)]
                if contained:
                    summary = summary.replace(contained[0], "")
                    organizer = contained[0]

            data['events'].append({
                "dtstart": dtstart.isoformat(),
                "dtend": dtend.isoformat(),
                "organizer": organizer.strip(),
                "summary": summary.strip()
            })

    data['events'].sort(key=lambda e: datetime.datetime.fromisoformat(e.get("dtstart"))) 
    with open(cache_filename, "w") as cache_file:
        json.dump(data, cache_file)

    logger.debug(f"{id} collected {len(data)} events")
    #logger.debug(f"... collected data='{data}'")
    return data['events']
