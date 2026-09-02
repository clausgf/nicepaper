"""
HTTP-level check that a device's poll records next_expected_at -- on a real
200 and on a 304 alike -- without disturbing fetched_at/the delivered PNG.
Kept as its own file with its own fixtures rather than added to
test_acceptance.py, since that file is an acceptance test this repo's
CLAUDE.md says not to change without asking.
"""
import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from extensions.epaper.devicebinding.backend import set_device_binding
from extensions.epaper.devicebinding.snapshot import read_device_snapshot
from main import app, STANDALONE_PATHS


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture()
def device():
    screen_id = f"next-expected-{uuid.uuid4().hex[:8]}"
    screen_file = os.path.join(STANDALONE_PATHS.screen_dir, f"{screen_id}.json")
    with open(screen_file, "w") as f:
        json.dump({"width": 100, "height": 100, "palette_id": "bw", "widgets": []}, f)

    device_name = f"next-expected-device-{uuid.uuid4().hex[:8]}"
    set_device_binding(STANDALONE_PATHS, device_name, screen_id=screen_id)
    yield device_name
    set_device_binding(STANDALONE_PATHS, device_name, room_id=None, screen_id=None, panel_type_id=None)
    for suffix in (".png", ".json"):
        path = STANDALONE_PATHS.device_snapshot_dir / f"{device_name}{suffix}"
        if path.exists():
            path.unlink()
    if os.path.exists(screen_file):
        os.remove(screen_file)


def test_first_poll_records_next_expected_alongside_the_delivery(client, device):
    r = client.get(f"/api/screen/{device}/image.png")
    assert r.status_code == 200

    snapshot = read_device_snapshot(STANDALONE_PATHS, device)
    assert snapshot is not None
    assert snapshot.fetched_at is not None
    assert snapshot.next_expected_at is not None
    assert snapshot.next_expected_at > snapshot.fetched_at


def test_a_304_poll_still_advances_next_expected_without_touching_fetched_at(client, device):
    r = client.get(f"/api/screen/{device}/image.png")
    etag = r.headers["etag"]
    first = read_device_snapshot(STANDALONE_PATHS, device)
    assert first is not None

    r2 = client.get(f"/api/screen/{device}/image.png", headers={"If-None-Match": etag})
    assert r2.status_code == 304

    second = read_device_snapshot(STANDALONE_PATHS, device)
    assert second is not None
    assert second.fetched_at == first.fetched_at  # unchanged: no new content delivered
    assert second.next_expected_at is not None and second.next_expected_at >= first.next_expected_at
