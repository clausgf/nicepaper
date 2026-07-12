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
            "size": [400, 300],
            "widgets": [
                {"widget_type": "Text", "position": [10, 10], "size": [380, 30], "text": "Acceptance"},
                {"widget_type": "Date", "position": [10, 50], "size": [380, 30]},
            ],
        }, f)
    yield screen_id
    if os.path.exists(screen_file):
        os.remove(screen_file)
    shutil.rmtree(os.path.join(STANDALONE_PATHS.image_dir, screen_id), ignore_errors=True)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


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


def test_color_model_quantization(client, screen_id):
    """color_model returns a palette image; unknown values fall back to RGB."""
    r = client.get(f"/api/screen/{screen_id}/image.png", params={"color_model": "bw"})
    assert r.status_code == 200
    image = Image.open(io.BytesIO(r.content))
    assert image.mode == "P", "quantized image should use a palette"

    r2 = client.get(f"/api/screen/{screen_id}/image.png", params={"color_model": "nonsense"})
    assert r2.status_code == 200
    image2 = Image.open(io.BytesIO(r2.content))
    assert image2.mode == "RGB", "unknown color model should fall back to RGB"


def test_unknown_screen_returns_404(client):
    r = client.get("/api/screen/does-not-exist/image.png")
    assert r.status_code == 404


def test_ui_and_api_docs_reachable(client):
    r = client.get("/ui/")
    assert r.status_code == 200
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "Epaper Doorsign Manager"
