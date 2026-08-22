import asyncio
import datetime
import json
from zoneinfo import ZoneInfo

import pytest

from extensions.epaper.global_config.backend import app_config
from extensions.epaper.core.datasources.homeassistant import (
    EntityStatus, _cache_filename, entity_label, entity_unit, format_value, get_entity,
    numeric_value, raw_value, read_all_entity_statuses,
)


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    """Every test here assumes a configured instance unless it says otherwise."""
    monkeypatch.setattr(app_config, "homeassistant_url", "http://ha.local:8123")
    monkeypatch.setattr(app_config, "homeassistant_token", "token")


def _now():
    return datetime.datetime.now(ZoneInfo(app_config.timezone))


def _write_cache(tmp_path, entity_id, **fields):
    _cache_filename(tmp_path, entity_id).write_text(json.dumps({"entity_id": entity_id, **fields}))


def _state(state="21.4", **attributes):
    return {"state": state, "attributes": attributes}


def test_cache_filename_sanitizes_the_entity_id(tmp_path):
    # a hand-edited screen file must not be able to write outside the cache dir
    path = _cache_filename(tmp_path, "sensor.../../etc/passwd")
    assert path.parent == tmp_path


def test_get_entity_uses_cache_without_network_call(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "homeassistant_update_interval_s", 300)
    _write_cache(tmp_path, "sensor.temp", last_update=_now().isoformat(),
                 data=_state("21.4", unit_of_measurement="°C", friendly_name="Living room"))
    monkeypatch.setattr("extensions.epaper.core.datasources.homeassistant._get_session", _fail_if_called)

    status = asyncio.run(get_entity(tmp_path, "sensor.temp"))
    assert status.state == "21.4" and status.fresh and not status.failing
    assert entity_unit(status) == "°C"
    assert entity_label(status) == "Living room"


def test_get_entity_backs_off_and_degrades_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "homeassistant_update_interval_s", 300)
    monkeypatch.setattr(app_config, "homeassistant_retry_min_s", 60)
    monkeypatch.setattr(app_config, "homeassistant_retry_max_s", 1800)
    old = _now() - datetime.timedelta(hours=2)
    _write_cache(tmp_path, "sensor.temp", last_update=old.isoformat(), data=_state("9.0"))

    async def boom():
        raise RuntimeError("Cannot connect to host ha.local:8123")
    monkeypatch.setattr("extensions.epaper.core.datasources.homeassistant._get_session",
                        lambda: _FakeSession(boom))

    first = asyncio.run(get_entity(tmp_path, "sensor.temp"))
    assert first.state == "9.0"                      # graceful: last-known value still rendered
    assert first.failing and first.fail_count == 1 and first.retry_after is not None

    # inside the backoff window -> no request at all
    monkeypatch.setattr("extensions.epaper.core.datasources.homeassistant._get_session", _fail_if_called)
    second = asyncio.run(get_entity(tmp_path, "sensor.temp"))
    assert second.state == "9.0" and second.failing


def test_get_entity_fetches_and_caches(tmp_path, monkeypatch):
    payload = {"entity_id": "sensor.temp", "state": "18.2",
               "attributes": {"friendly_name": "Office", "unit_of_measurement": "°C"}}

    async def ok():
        return None
    monkeypatch.setattr("extensions.epaper.core.datasources.homeassistant._get_session",
                        lambda: _FakeSession(ok, payload))

    status = asyncio.run(get_entity(tmp_path, "sensor.temp"))
    assert status.state == "18.2" and status.fresh and not status.failing
    # the state is cached, so a second render doesn't need the network
    monkeypatch.setattr("extensions.epaper.core.datasources.homeassistant._get_session", _fail_if_called)
    assert asyncio.run(get_entity(tmp_path, "sensor.temp")).state == "18.2"


def test_get_entity_without_configuration_never_touches_network_or_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "homeassistant_url", "")
    monkeypatch.setattr("extensions.epaper.core.datasources.homeassistant._get_session", _fail_if_called)

    status = asyncio.run(get_entity(tmp_path, "sensor.temp"))
    assert status.failing and status.state is None
    assert "not configured" in status.error
    # no backoff state written: configuring the URL must take effect at once
    assert not list(tmp_path.glob("*.json"))


def test_read_all_entity_statuses(tmp_path):
    _write_cache(tmp_path, "sensor.temp", last_update=_now().isoformat(), data=_state("21.4"))
    _write_cache(tmp_path, "sensor.broken",
                 last_update=(_now() - datetime.timedelta(hours=3)).isoformat(),
                 data=_state("9.0"), fail_count=2, error="timeout")
    statuses = {s.entity_id: s for s in read_all_entity_statuses(tmp_path)}
    assert statuses["sensor.temp"].fresh is True
    broken = statuses["sensor.broken"]
    assert broken.failing and broken.fail_count == 2 and broken.error == "timeout"


def test_raw_value_reads_state_or_attribute():
    status = EntityStatus(entity_id="climate.hall", state="heat",
                          attributes={"temperature": 21.5, "friendly_name": "Hall"})
    assert raw_value(status) == "heat"
    assert raw_value(status, "temperature") == "21.5"
    assert raw_value(status, "missing") is None
    # an attribute has no unit_of_measurement of its own in HA
    assert entity_unit(status, "temperature") is None
    assert entity_label(status, "temperature") == "Hall temperature"


@pytest.mark.parametrize("text,expected", [
    ("21.4", 21.4),
    ("-3", -3.0),
    ("on", None),
    ("unavailable", None),
    ("unknown", None),
    (None, None),
])
def test_numeric_value_only_parses_real_numbers(text, expected):
    assert numeric_value(text) == expected


@pytest.mark.parametrize("text,decimals,expected", [
    ("21.44", 1, "21.4"),
    ("21.44", 0, "21"),
    ("on", 1, "on"),          # non-numeric states pass through unchanged
    ("unavailable", 1, "unavailable"),
])
def test_format_value_rounds_numbers_only(text, decimals, expected):
    assert format_value(text, decimals) == expected


class _FakeResponse:
    def __init__(self, fn, payload):
        self._fn = fn
        self._payload = payload
    async def __aenter__(self):
        await self._fn()
        return self
    async def __aexit__(self, *a):
        return False
    async def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, fn, payload=None):
        self._fn = fn
        self._payload = payload or {}
    def get(self, *a, **k):
        return _FakeResponse(self._fn, self._payload)


def _fail_if_called():
    raise AssertionError("network must not be used here")
