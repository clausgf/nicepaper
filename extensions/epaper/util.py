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
