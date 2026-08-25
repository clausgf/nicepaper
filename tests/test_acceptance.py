"""
Acceptance tests: exercise the HTTP API end-to-end the way a display and
a browser would, against a real screen configuration on disk.
"""
import io
import json
import os
import shutil
import uuid

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from extensions.epaper.devicebinding.backend import set_device_binding
from main import app, STANDALONE_PATHS


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture()
def screen_id():
    """A screen configuration file on disk, removed after the test."""
    screen_id = f"acceptance-{uuid.uuid4().hex[:8]}"
    screen_file = os.path.join(STANDALONE_PATHS.screen_dir, f"{screen_id}.json")
    with open(screen_file, "w") as f:
        json.dump({
            "width": 400,
            "height": 300,
            "palette_id": "bw",
            "widgets": [
                {"widget_type": "Text", "position_x": 10, "position_y": 10, "size_width": 380, "size_height": 30, "text": "Acceptance"},
                {"widget_type": "Date", "position_x": 10, "position_y": 50, "size_width": 380, "size_height": 30},
            ],
        }, f)
    yield screen_id
    if os.path.exists(screen_file):
        os.remove(screen_file)
    shutil.rmtree(os.path.join(STANDALONE_PATHS.image_dir, screen_id), ignore_errors=True)


@pytest.fixture()
def device_binding(screen_id):
    """A device bound to `screen_id`, removed after the test -- along with
    any snapshot the test's fetches recorded for it (device_snapshots/)."""
    device_name = f"acceptance-device-{uuid.uuid4().hex[:8]}"
    set_device_binding(STANDALONE_PATHS, device_name, screen_id=screen_id)
    yield device_name
    set_device_binding(STANDALONE_PATHS, device_name, room_id=None, screen_id=None, panel_type_id=None)
    for suffix in (".png", ".json"):
        path = STANDALONE_PATHS.device_snapshot_dir / f"{device_name}{suffix}"
        if path.exists():
            path.unlink()


def test_root_redirects_to_ui(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/ui"


def test_display_poll_cycle(client, screen_id):
    """A display fetches its image, then polls with If-None-Match."""
    r = client.get(f"/api/screen/{screen_id}/image.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert "max-age=" in r.headers["cache-control"]
    etag = r.headers["etag"]

    image = Image.open(io.BytesIO(r.content))
    assert image.size == (400, 300)

    # unchanged screen -> 304 without a body
    r2 = client.get(f"/api/screen/{screen_id}/image.png", headers={"If-None-Match": etag})
    assert r2.status_code == 304
    assert r2.headers["etag"] == etag


def test_screen_change_produces_new_image(client, screen_id):
    """Editing the screen file invalidates cache and ETag."""
    r = client.get(f"/api/screen/{screen_id}/image.png")
    etag = r.headers["etag"]

    screen_file = os.path.join(STANDALONE_PATHS.screen_dir, f"{screen_id}.json")
    with open(screen_file) as f:
        config = json.load(f)
    config["widgets"][0]["text"] = "Changed text"
    with open(screen_file, "w") as f:
        json.dump(config, f)
    # ensure the mtime moves even on filesystems with coarse timestamps
    stat = os.stat(screen_file)
    os.utime(screen_file, (stat.st_atime, stat.st_mtime + 10))

    r2 = client.get(f"/api/screen/{screen_id}/image.png", headers={"If-None-Match": etag})
    assert r2.status_code == 200
    assert r2.headers["etag"] != etag


def test_screen_palette_and_raw_render(client, screen_id):
    """A display gets the image quantized to the screen's own palette, with
    no say in the matter; ?raw=true returns the RGB render the editor
    preview compares it against."""
    r = client.get(f"/api/screen/{screen_id}/image.png")
    assert r.status_code == 200
    image = Image.open(io.BytesIO(r.content))
    assert image.mode == "P", "quantized image should use a palette"

    r2 = client.get(f"/api/screen/{screen_id}/image.png", params={"raw": "true"})
    assert r2.status_code == 200
    image2 = Image.open(io.BytesIO(r2.content))
    assert image2.mode == "RGB", "the raw render should be unquantized"
    assert r2.headers["etag"] != r.headers["etag"], "different bytes must not share an ETag"


def test_unknown_screen_returns_404(client):
    r = client.get("/api/screen/does-not-exist/image.png")
    assert r.status_code == 404


def test_device_fetch_records_a_snapshot_and_last_delivered_serves_it(client, device_binding):
    """A device's own alias URL (its name, not the screen id) records a
    snapshot on a real 200; last_delivered.png then serves those exact
    bytes."""
    device_name = device_binding
    r = client.get(f"/api/screen/{device_name}/image.png")
    assert r.status_code == 200

    r2 = client.get(f"/api/screen/{device_name}/last_delivered.png")
    assert r2.status_code == 200
    assert r2.headers["content-type"] == "image/png"
    assert r2.content == r.content


def test_last_delivered_404s_before_any_fetch(client, device_binding):
    r = client.get(f"/api/screen/{device_binding}/last_delivered.png")
    assert r.status_code == 404


def test_last_delivered_404s_for_an_unknown_device_name(client):
    r = client.get("/api/screen/not-a-real-device/last_delivered.png")
    assert r.status_code == 404


def test_fetching_a_bare_screen_id_does_not_record_a_device_snapshot(client, screen_id):
    """The editor's own live preview hits this same endpoint with a literal
    screen id, not a device name -- that must not be recorded as if a
    device had fetched it (screen_id has no device binding of its own)."""
    r = client.get(f"/api/screen/{screen_id}/image.png")
    assert r.status_code == 200

    r2 = client.get(f"/api/screen/{screen_id}/last_delivered.png")
    assert r2.status_code == 404


def test_raw_fetch_does_not_update_the_snapshot(client, device_binding):
    """?raw=true is a debugging view a real display never requests (see
    _RAW_DESCRIPTION); it must not overwrite what a real fetch recorded."""
    device_name = device_binding
    r = client.get(f"/api/screen/{device_name}/image.png")
    delivered = client.get(f"/api/screen/{device_name}/last_delivered.png").content

    r_raw = client.get(f"/api/screen/{device_name}/image.png", params={"raw": "true"})
    assert r_raw.status_code == 200
    assert r_raw.content != r.content  # sanity: raw really is different bytes

    still_delivered = client.get(f"/api/screen/{device_name}/last_delivered.png").content
    assert still_delivered == delivered


def test_304_fetch_does_not_update_the_snapshot(client, device_binding):
    device_name = device_binding
    r = client.get(f"/api/screen/{device_name}/image.png")
    etag = r.headers["etag"]
    delivered = client.get(f"/api/screen/{device_name}/last_delivered.png").content

    r2 = client.get(f"/api/screen/{device_name}/image.png", headers={"If-None-Match": etag})
    assert r2.status_code == 304

    still_delivered = client.get(f"/api/screen/{device_name}/last_delivered.png").content
    assert still_delivered == delivered


def test_ui_and_api_docs_reachable(client):
    r = client.get("/ui/")
    assert r.status_code == 200
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "Nicepaper"
