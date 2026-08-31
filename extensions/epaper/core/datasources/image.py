"""
Image loading for the Image widget: fetch a picture from a URL or a file in
the project directory, with an optional persistent cache so "load once"
survives screen re-renders. Mirrors the datasource style of ical.py/weather.py
(the widget reads the returned object directly, no intermediate model).
"""
import datetime
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import aiofiles
import aiohttp
from PIL import Image

from extensions.epaper.global_config.backend import app_config
from extensions.epaper.screen.models import ImageWidgetModel
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.util import logger

# fixed timeout for fetching a remote image, in seconds
FETCH_TIMEOUT_S = 10

_session: Optional[aiohttp.ClientSession] = None


def _get_session() -> aiohttp.ClientSession:
    """Lazily create the shared HTTP session (must be created inside a running
    event loop), same pattern as the weather datasource."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(raise_for_status=True)
    return _session


def _source_label(config: ImageWidgetModel) -> str:
    return (config.url if config.source_type == "url" else config.file) or ""


def _source_key(config: ImageWidgetModel) -> str:
    """A stable cache key for this widget's image source."""
    return hashlib.sha256(f"{config.source_type}:{_source_label(config)}".encode()).hexdigest()[:16]


def _cache_path(paths: EpaperPaths, config: ImageWidgetModel) -> Path:
    return paths.image_cache_dir / _source_key(config)


def _status_path(paths: EpaperPaths, config: ImageWidgetModel) -> Path:
    """Small JSON sidecar next to the cached bytes, tracking fetch/decode
    outcomes (fail_count, backoff, last error) -- see ImageStatus."""
    return paths.image_cache_dir / f"{_source_key(config)}.json"


def _asset_path(paths: EpaperPaths, filename: str) -> Path:
    """Resolve a project-directory image file, rejecting anything that escapes
    the asset directory (path traversal via '..' or an absolute path)."""
    base = paths.asset_dir.resolve()
    path = (base / filename).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"image file {filename!r} escapes the project directory")
    return path


async def _fetch_bytes(paths: EpaperPaths, config: ImageWidgetModel) -> bytes:
    if config.source_type == "url":
        if not config.url:
            raise ValueError("no image URL configured")
        timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_S)
        async with _get_session().get(config.url, timeout=timeout) as response:
            return await response.read()
    if not config.file:
        raise ValueError("no image file configured")
    async with aiofiles.open(_asset_path(paths, config.file), "rb") as f:
        return await f.read()


@dataclass
class ImageStatus:
    """Outcome of an Image widget's last fetch/decode for one source (see
    _source_key), for the dashboard health view. Read from a small JSON
    sidecar next to the cached bytes -- the image itself isn't kept here,
    only whether loading it currently works."""
    key: str
    source: str                                       # url or filename, for the dashboard label
    last_update: Optional[datetime.datetime]           # last successful load
    failing: bool                                      # last attempt failed / currently backing off
    fail_count: int                                    # consecutive failures
    retry_after: Optional[datetime.datetime]           # earliest next network attempt
    error: Optional[str]                                # last error message (dashboard tooltip)


def _read_status_cache(path: Path) -> dict:
    try:
        with open(path, "r") as f:
            cache = json.load(f)
        return cache if isinstance(cache, dict) else {}
    except Exception:
        return {}


def _parse_dt(value: Optional[str]) -> Optional[datetime.datetime]:
    return datetime.datetime.fromisoformat(value) if value else None


def _status_from_cache(key: str, cache: dict) -> ImageStatus:
    fail_count = int(cache.get('fail_count', 0))
    return ImageStatus(
        key=key, source=cache.get('source', ''),
        last_update=_parse_dt(cache.get('last_update')),
        failing=fail_count > 0, fail_count=fail_count,
        retry_after=_parse_dt(cache.get('retry_after')), error=cache.get('error'),
    )


def _backoff_seconds(fail_count: int) -> float:
    """Exponential backoff (base doubling per consecutive failure), capped."""
    base = max(1, app_config.image_retry_min_s)
    return float(min(base * (2 ** max(0, fail_count - 1)), app_config.image_retry_max_s))


def read_all_image_statuses(image_cache_dir: Path) -> list[ImageStatus]:
    """Status of every cached image source (no fetch), for the dashboard
    health view."""
    statuses = []
    for path in sorted(Path(image_cache_dir).glob("*.json")):
        cache = _read_status_cache(path)
        if not cache:
            continue
        statuses.append(_status_from_cache(path.stem, cache))
    return statuses


async def get_image(paths: EpaperPaths, config: ImageWidgetModel) -> Optional[Image.Image]:
    """
    Return the widget's image as a decoded PIL Image, or None if it can't be
    loaded (the widget renders the configured error message instead).

    Unless reload_each_time is set, the fetched bytes are cached under
    image_cache_dir so the image is loaded only once and reused across
    re-renders (clear_cache() / the editor's 'Reload now' drops that cache).

    Failures are tracked like the weather/Home Assistant/iCal datasources
    (fail_count, exponential backoff via retry_after, last error) in a small
    JSON sidecar next to the cached bytes, read by read_all_image_statuses()
    for the dashboard health view -- without this, a broken reload_each_time
    source (or one that has never fetched successfully) would be retried on
    every single render. A cache_once source that already has a cached image
    never re-fetches, so it never needs backoff, only a healthy status line.
    """
    cache_path = _cache_path(paths, config)
    status_path = _status_path(paths, config)
    cache_once = not config.reload_each_time
    have_cache = cache_once and cache_path.is_file()
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    status_cache = _read_status_cache(status_path)
    status = _status_from_cache(_source_key(config), status_cache)

    if not have_cache and status.retry_after is not None and now < status.retry_after:
        logger.info(f"Image {_source_label(config)} backing off until {status.retry_after.isoformat()}")
        return None

    try:
        if have_cache:
            data = cache_path.read_bytes()
        else:
            data = await _fetch_bytes(paths, config)
            if cache_once:
                paths.image_cache_dir.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(data)
        image = Image.open(io.BytesIO(data))
        image.load()  # force decode now, while the buffer is alive
    except Exception as e:
        logger.warning(f"Image widget could not load {config.source_type} image: {e}")
        fail_count = status.fail_count + 1
        retry_after = now + datetime.timedelta(seconds=_backoff_seconds(fail_count))
        status_cache.update(source=_source_label(config), fail_count=fail_count,
                            retry_after=retry_after.isoformat(), error=str(e))
        paths.image_cache_dir.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(status_cache))
        return None

    status_cache = {'source': _source_label(config), 'last_update': now.isoformat()}  # clears fail/backoff state
    paths.image_cache_dir.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status_cache))
    return image


def clear_cache(paths: EpaperPaths, config: ImageWidgetModel) -> None:
    """Drop the cached copy so the next render re-fetches (editor 'Reload now')."""
    _cache_path(paths, config).unlink(missing_ok=True)
