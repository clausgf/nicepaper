import datetime
import logging
import re
from typing import Optional

logger = logging.getLogger('uvicorn.error')


filename_regex_str = r'^[a-zA-Z0-9_\-+]+\.[a-zA-Z0-9]+$'


def humanize_age(dt: Optional[datetime.datetime], now: datetime.datetime) -> str:
    """'just now' / 'N min ago' / 'N h ago' / 'N d ago' for a past datetime,
    or 'never' for None. Shared by anything showing "how long ago" for a
    timestamp (datasource health rows, a device's last-seen)."""
    if dt is None:
        return 'never'
    minutes = max(0, int((now - dt).total_seconds() // 60))
    if minutes < 1:
        return 'just now'
    if minutes < 60:
        return f'{minutes} min ago'
    if minutes < 60 * 24:
        return f'{minutes // 60} h ago'
    return f'{minutes // (60 * 24)} d ago'


def humanize_datetime_age(dt: Optional[datetime.datetime], now: datetime.datetime) -> str:
    """'DD.MM.YY HH:MM:SS (Nmin ago)', matching nice4iot's own device status
    card (app.util.render_datetime_age -- local timezone, its own age
    granularity), or 'never' for None. Deferred-imported since epaper must
    also run standalone/in tests where app.* doesn't exist; the fallback
    below uses UTC and humanize_age()'s granularity instead."""
    if dt is None:
        return 'never'
    try:
        from app.util import render_datetime_age
        return render_datetime_age(dt)
    except ImportError:
        return f'{dt.strftime("%d.%m.%y %H:%M:%S")} ({humanize_age(dt, now)})'


def check_filename(filename: str) -> bool:
    """
    Check if the filename consists of alphanumeric characters, underscores, hyphens, and plus signs.
    """
    return re.match(filename_regex_str, filename) is not None


def clean_path_parameter(path_element: str) -> str:
    """
    Clean the path_element to prevent path traversal.
    """
    return path_element.replace('/', '').replace('..', '')
