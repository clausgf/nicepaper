"""
Image loading for the Image widget: fetch a picture from a URL or a file in
the project directory, with an optional persistent cache so "load once"
survives screen re-renders. Mirrors the datasource style of ical.py/weather.py
(the widget reads the returned object directly, no intermediate model).
"""
import hashlib
import io
from pathlib import Path
from typing import Optional

import aiofiles
import aiohttp
from PIL import Image

from extensions.epaper.models.screenmodel import ImageWidgetModel
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


def _source_key(config: ImageWidgetModel) -> str:
    """A stable cache key for this widget's image source."""
    source = config.url if config.source_type == "url" else config.file
    return hashlib.sha256(f"{config.source_type}:{source}".encode()).hexdigest()[:16]


def _cache_path(paths: EpaperPaths, config: ImageWidgetModel) -> Path:
    return paths.image_cache_dir / _source_key(config)


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


async def get_image(paths: EpaperPaths, config: ImageWidgetModel) -> Optional[Image.Image]:
    """Return the widget's image as a decoded PIL Image, or None if it can't be
    loaded (the widget renders the configured error message instead).

    Unless reload_each_time is set, the fetched bytes are cached under
    image_cache_dir so the image is loaded only once and reused across
    re-renders (clear_cache() / the editor's 'Reload now' drops that cache).
    """
    cache_path = _cache_path(paths, config)
    cache_once = not config.reload_each_time
    try:
        if cache_once and cache_path.is_file():
            data = cache_path.read_bytes()
        else:
            data = await _fetch_bytes(paths, config)
            if cache_once:
                paths.image_cache_dir.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(data)
        image = Image.open(io.BytesIO(data))
        image.load()  # force decode now, while the buffer is alive
        return image
    except Exception as e:
        logger.warning(f"Image widget could not load {config.source_type} image: {e}")
        return None


def clear_cache(paths: EpaperPaths, config: ImageWidgetModel) -> None:
    """Drop the cached copy so the next render re-fetches (editor 'Reload now')."""
    _cache_path(paths, config).unlink(missing_ok=True)
