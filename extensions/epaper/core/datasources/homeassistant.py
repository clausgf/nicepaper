"""
Home Assistant entity states via its REST API (GET /api/states/<entity_id>,
authenticated with a long-lived access token), cached per entity.

Same shape as the weather datasource: one JSON cache file per entity, an
update interval, exponential backoff on failure, and graceful degradation
(the last-known state keeps being rendered during an outage) -- get_entity()
never raises, it returns an EntityStatus describing what is known. The
dashboard reads the same cache files without fetching, see
read_all_entity_statuses().

Only the states endpoint is used: it is the one call that needs no
knowledge of HA's internals, works for every domain, and returns both the
state and the attributes (friendly_name, unit_of_measurement, ...) the
widget needs to label a value.
"""
import datetime
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import aiofiles
import aiohttp

from extensions.epaper.global_config.backend import app_config
from extensions.epaper.util import logger

# fixed timeout for one states request, in seconds
FETCH_TIMEOUT_S = 10

# states HA uses for "no value" -- rendered as they are, but never parsed as
# a number (so a gauge falls back to the text instead of drawing 0)
UNAVAILABLE_STATES = ("unavailable", "unknown", "none", "")


@dataclass
class EntityStatus:
    """Outcome of an entity lookup, for both the widget (state + attributes +
    staleness) and the dashboard health view (failing/error/retry)."""
    entity_id: str
    state: Optional[str]                             # last-known state; None if never fetched
    attributes: dict = field(default_factory=dict)
    last_update: Optional[datetime.datetime] = None  # last successful fetch
    fresh: bool = False                              # last_update within the update interval
    failing: bool = False                            # last attempt failed / currently backing off
    fail_count: int = 0                              # consecutive failures
    retry_after: Optional[datetime.datetime] = None  # earliest next network attempt
    error: Optional[str] = None                      # last error message (dashboard tooltip)


def _cache_filename(homeassistant_dir: Path, entity_id: str) -> Path:
    """Cache file for an entity. Entity ids are '<domain>.<object_id>' with a
    restricted character set, but sanitize anyway so a hand-edited screen file
    can't write outside the cache directory."""
    safe = re.sub(r"[^a-z0-9_.-]", "_", entity_id.lower())
    return Path(homeassistant_dir) / f"{safe}.json"


def _read_cache(cache_filename: Path) -> dict:
    try:
        with open(cache_filename, "r") as f:
            cache = json.load(f)
        return cache if isinstance(cache, dict) else {}
    except Exception:
        return {}


def _parse_dt(value: Optional[str]) -> Optional[datetime.datetime]:
    return datetime.datetime.fromisoformat(value) if value else None


def _status_from_cache(entity_id: str, cache: dict, now: datetime.datetime) -> EntityStatus:
    last_update = _parse_dt(cache.get('last_update'))
    fresh = (last_update is not None
             and (now - last_update).total_seconds() < app_config.homeassistant_update_interval_s)
    fail_count = int(cache.get('fail_count', 0))
    data = cache.get('data') or {}
    return EntityStatus(
        entity_id=cache.get('entity_id', entity_id),
        state=data.get('state'), attributes=data.get('attributes') or {},
        last_update=last_update, fresh=fresh, failing=fail_count > 0, fail_count=fail_count,
        retry_after=_parse_dt(cache.get('retry_after')), error=cache.get('error'),
    )


def _backoff_seconds(fail_count: int) -> float:
    """Exponential backoff (base doubling per consecutive failure), capped."""
    base = max(1, app_config.homeassistant_retry_min_s)
    return float(min(base * (2 ** max(0, fail_count - 1)), app_config.homeassistant_retry_max_s))


def is_configured() -> bool:
    """Whether a Home Assistant URL and token are configured at all."""
    return bool(app_config.homeassistant_url and app_config.homeassistant_token)


def read_all_entity_statuses(homeassistant_dir: Path) -> list[EntityStatus]:
    """Status of every cached entity (no fetch), for the dashboard health view.
    The entity id is read from the cache file's content, not its name, so the
    file-name sanitization above stays one-way."""
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    statuses = []
    for path in sorted(Path(homeassistant_dir).glob("*.json")):
        cache = _read_cache(path)
        if not cache.get('entity_id'):
            continue
        statuses.append(_status_from_cache(cache['entity_id'], cache, now))
    return statuses


_session: Optional[aiohttp.ClientSession] = None


def _get_session() -> aiohttp.ClientSession:
    """Lazily create the shared HTTP session (must be created inside a running
    event loop), same pattern as the weather/image datasources."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(raise_for_status=True)
    return _session


async def get_entity(homeassistant_dir: Path, entity_id: str) -> EntityStatus:
    """
    Fetch (or return cached) state + attributes of one Home Assistant entity.

    Never raises: a failure is recorded in the same cache file (fail_count,
    exponential backoff via retry_after, last error) and the last-known state
    is returned with failing=True. While backing off no request is made, so a
    screen full of HA widgets doesn't hammer an unreachable instance.
    """
    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    cache_filename = _cache_filename(homeassistant_dir, entity_id)
    cache = _read_cache(cache_filename)
    status = _status_from_cache(entity_id, cache, now)

    if not is_configured():
        # not an outage worth backing off from -- report it without touching
        # the cache, so configuring the URL/token takes effect immediately
        status.failing = True
        status.error = "Home Assistant URL/token not configured"
        return status
    if status.fresh:
        logger.info(f"Home Assistant {entity_id} skipping update, cached state is fresh")
        return status
    if status.retry_after is not None and now < status.retry_after:
        logger.info(f"Home Assistant {entity_id} backing off until {status.retry_after.isoformat()}")
        return status

    url = f"{app_config.homeassistant_url.rstrip('/')}/api/states/{entity_id}"
    headers = {"Authorization": f"Bearer {app_config.homeassistant_token}"}
    logger.info(f"Home Assistant {entity_id} updating from {url}")
    try:
        timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_S)
        async with _get_session().get(url, headers=headers, timeout=timeout) as response:
            payload = await response.json()
        state = payload["state"]
    except Exception as e:
        fail_count = status.fail_count + 1
        retry_after = now + datetime.timedelta(seconds=_backoff_seconds(fail_count))
        logger.error(f"Error occurred while fetching Home Assistant entity {entity_id}: {e}; "
                     f"retrying after {retry_after.isoformat()} (attempt {fail_count})")
        cache.update(entity_id=entity_id, fail_count=fail_count,
                     retry_after=retry_after.isoformat(), error=str(e))
        homeassistant_dir.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(cache_filename, "w") as cache_file:
            await cache_file.write(json.dumps(cache))
        return _status_from_cache(entity_id, cache, now)

    # success clears fail/backoff state
    cache = {'entity_id': entity_id, 'last_update': now.isoformat(),
             'data': {'state': state, 'attributes': payload.get("attributes") or {}}}
    homeassistant_dir.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(cache_filename, "w") as cache_file:
        await cache_file.write(json.dumps(cache))
    return _status_from_cache(entity_id, cache, now)


def raw_value(status: EntityStatus, attribute: Optional[str] = None) -> Optional[str]:
    """The entity's state, or one of its attributes if `attribute` is given
    (e.g. 'temperature' of a climate entity). None if there is nothing to show."""
    if attribute:
        value = status.attributes.get(attribute)
        return None if value is None else str(value)
    return status.state


def numeric_value(text: Optional[str]) -> Optional[float]:
    """`text` as a float, or None if it isn't numeric (e.g. 'on', 'unavailable')
    -- a gauge falls back to drawing the text in that case."""
    if text is None or text.strip().lower() in UNAVAILABLE_STATES:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def entity_label(status: EntityStatus, attribute: Optional[str] = None) -> str:
    """Default label for a value: the entity's friendly_name (with the attribute
    name appended when reading an attribute), falling back to the entity id."""
    name = status.attributes.get("friendly_name") or status.entity_id
    return f"{name} {attribute}" if attribute else str(name)


def entity_unit(status: EntityStatus, attribute: Optional[str] = None) -> Optional[str]:
    """The entity's unit_of_measurement, which HA only defines for the state
    itself -- an attribute has no unit of its own, so None there."""
    if attribute:
        return None
    unit = status.attributes.get("unit_of_measurement")
    return str(unit) if unit else None


def format_value(text: Optional[str], decimals: int) -> str:
    """Display string for a value: numbers rounded to `decimals` places,
    anything else (states like 'on', 'heating') passed through unchanged."""
    if text is None:
        return ""
    number = numeric_value(text)
    return f"{number:.{decimals}f}" if number is not None else text
