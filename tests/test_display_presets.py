"""
What a display preset ends up doing at render time: the screen's palette
decides what the image endpoint serves, and the screen's/widget's colors
decide what gets drawn.
"""
import asyncio
import io
import json
import os

import pytest
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient

from extensions.epaper import catalog
from extensions.epaper.api.endpoints import build_standalone_router
from extensions.epaper.config import app_config
from extensions.epaper.screen.backend import get_screen_by_id
from extensions.epaper.screen.models import ScreenModel
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.preview import ruler_ticks
from extensions.epaper.screen.ui import _apply_display


def _write_screen(paths: EpaperPaths, screen_id: str, **fields) -> None:
    screen = {
        "width": 120,
        "height": 60,
        "update_schedule_id": None,
        "widgets": [
            {"widget_type": "Text", "position_x": 0, "position_y": 0, "text": "hello"},
        ],
    }
    screen.update(fields)
    (paths.screen_dir / f"{screen_id}.json").write_text(json.dumps(screen))


@pytest.fixture()
def paths(tmp_path) -> EpaperPaths:
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    return paths


@pytest.fixture()
def client(paths) -> TestClient:
    app = FastAPI()
    app.include_router(build_standalone_router(paths), prefix="/api")
    return TestClient(app)


# --- colors ---------------------------------------------------------------

def test_screen_colors_fall_back_to_the_global_defaults(paths):
    _write_screen(paths, "plain")
    screen = asyncio.run(get_screen_by_id(paths, "plain"))
    assert screen.colors == (app_config.color_background, app_config.color_primary,
                             app_config.color_accent)


def test_screen_colors_override_the_global_defaults_per_aspect(paths):
    _write_screen(paths, "tinted", color_primary="#123456")
    screen = asyncio.run(get_screen_by_id(paths, "tinted"))
    background, primary, accent = screen.colors
    assert primary == "#123456"
    assert background == app_config.color_background, "an unset color keeps the global default"
    assert accent == app_config.color_accent


def test_widget_colors_override_the_screen_colors(paths):
    """A bw display preset sets the screen accent to black; a single widget
    can still ask for something else, which is what the per-widget fields
    are for."""
    _write_screen(paths, "mixed", color_primary="#111111", color_accent="#222222", widgets=[
        {"widget_type": "Text", "position_x": 0, "position_y": 0, "text": "a"},
        {"widget_type": "Text", "position_x": 0, "position_y": 20, "text": "b",
         "color_primary": "#00ff00"},
    ])
    screen = asyncio.run(get_screen_by_id(paths, "mixed"))
    _, primary, accent = screen.colors

    plain, overridden = screen.config.widgets
    assert plain.resolved_colors(primary, accent) == ("#111111", "#222222")
    assert overridden.resolved_colors(primary, accent) == ("#00ff00", "#222222"), \
        "an unset aspect still falls back to the screen's color"


def test_screen_background_color_is_actually_drawn(paths):
    _write_screen(paths, "green", color_background="#00ff00")
    screen = asyncio.run(get_screen_by_id(paths, "green"))
    asyncio.run(screen.update_if_needed())
    image = asyncio.run(screen.get_image()).convert("RGB")
    assert image.getpixel((image.width - 1, image.height - 1)) == (0, 255, 0)


# --- applying a preset ----------------------------------------------------

def test_applying_a_preset_fills_every_field_it_owns():
    display = catalog.get_display("waveshare_7in5b_v2")
    screen = ScreenModel(width=1, height=1)
    _apply_display(screen, display)

    assert (screen.width, screen.height) == (display.width, display.height)
    assert screen.display_id == display.id
    assert screen.color_model == display.color_model
    assert screen.resolved_colors("x", "y", "z") == (
        display.color_background, display.color_primary, display.color_accent)


def test_black_and_white_presets_do_not_ask_for_a_red_accent():
    """Red would only quantize to black on a bw panel, so those presets say
    black rather than letting it happen by accident."""
    for display in catalog.get_displays().values():
        if display.color_model == "bw" and display.color_accent:
            assert display.color_accent == display.color_primary, display.id


# --- the editor's display select ------------------------------------------

# pushing the rebuilt form to a client needs a running NiceGUI loop; without
# one the send is dropped and leaves an un-awaited coroutine behind. Narrowly
# filtered rather than silenced, so other RuntimeWarnings still surface.
@pytest.mark.filterwarnings(
    "ignore:coroutine 'AwaitableResponse._fire' was never awaited:RuntimeWarning")
def test_picking_a_display_applies_the_preset(tmp_path, monkeypatch):
    """Regression: the select's handler used to read `e.value` off the
    GenericEventArguments an .on() handler receives, which has no such
    attribute -- so picking a preset raised in the server log and changed
    nothing. _apply_display() was green throughout; only the wiring was
    broken, which is why this test drives the actual element.
    """
    from nicegui import ui
    from nicegui.client import Client
    from nicegui.page import page
    from nicegui.events import GenericEventArguments, handle_event
    from extensions.epaper.screen.ui import screen_editor_content

    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    (paths.screen_dir / "s.json").write_text(json.dumps({"width": 800, "height": 480, "widgets": []}))
    # ui.notify needs a running NiceGUI loop, which a unit test has no business
    # starting; the notification is not what is under test here
    monkeypatch.setattr(ui, "notify", lambda *a, **kw: None)

    with Client(page("/test-display-select"), request=None) as client:
        screen_editor_content(paths, "s.json", "/api/screen")
        select = next(e for e in client.elements.values()
                      if type(e).__name__ == "Select" and e._props.get("label") == "Display")
        option = next(o for o in select._props["options"] if o["label"].startswith("Waveshare 4.2"))
        # dispatch the way NiceGUI does: every listener for the event, through
        # handle_event (which is what adapts the handler's signature)
        for listener in select._event_listeners.values():
            if listener.type == "update:modelValue":
                handle_event(listener.handler, GenericEventArguments(
                    sender=select, client=client, args=option))

    written = json.loads((paths.screen_dir / "s.json").read_text())
    display = catalog.get_display("waveshare_4in2")
    assert written["display_id"] == display.id
    assert (written["width"], written["height"]) == (display.width, display.height)
    assert written["color_model"] == display.color_model
    assert written["color_accent"] == display.color_accent


# --- preview ruler --------------------------------------------------------

def test_ruler_ticks_are_round_numbers_covering_the_screen():
    for extent in (400, 300, 800, 480, 880, 528, 640, 384):
        ticks = ruler_ticks(extent)
        assert ticks[0] == 0
        assert ticks[-1] <= extent, "a tick past the edge would sit outside the image"
        assert len(ticks) >= 4, f"{extent} px deserves more than {len(ticks)} ticks"

        step = ticks[1]
        assert str(step).lstrip("0").rstrip("0") in ("1", "2", "5", ""), \
            f"{step} is not a 1/2/5 x 10^k step"
        # every tick but the appended far edge sits on the step grid
        assert all(t % step == 0 for t in ticks[:-1])


def test_ruler_ticks_survive_a_degenerate_screen():
    assert ruler_ticks(0) == [0]
    assert ruler_ticks(1)[0] == 0


# --- palette / endpoint ---------------------------------------------------

def test_screen_palette_decides_what_the_endpoint_serves(client, paths):
    _write_screen(paths, "panel", color_model="bwr")
    r = client.get("/api/screen/panel/image.png")
    assert r.status_code == 200
    assert Image.open(io.BytesIO(r.content)).mode == "P", "a screen with a palette is served quantized"


def test_screen_without_a_palette_is_served_unquantized(client, paths):
    _write_screen(paths, "nopalette")
    r = client.get("/api/screen/nopalette/image.png")
    assert Image.open(io.BytesIO(r.content)).mode == "RGB"


def test_unknown_palette_falls_back_to_rgb(client, paths):
    """A screen that outlives the palette it names still has to render."""
    _write_screen(paths, "dangling", color_model="no-such-palette")
    r = client.get("/api/screen/dangling/image.png")
    assert r.status_code == 200
    assert Image.open(io.BytesIO(r.content)).mode == "RGB"


def test_raw_returns_the_rgb_render_with_its_own_etag(client, paths):
    _write_screen(paths, "panel", color_model="bwr")
    served = client.get("/api/screen/panel/image.png")
    raw = client.get("/api/screen/panel/image.png", params={"raw": "true"})

    assert Image.open(io.BytesIO(raw.content)).mode == "RGB"
    assert raw.headers["etag"] != served.headers["etag"], \
        "different bytes must not share an ETag"


def test_boxes_outlines_every_widget_without_touching_the_cache(client, paths):
    """The outline view is an editor thing: it must never end up in the
    image a display fetches, nor in the cached files behind it."""
    _write_screen(paths, "panel", color_model="bwr", widgets=[
        {"widget_type": "Text", "position_x": 5, "position_y": 5, "text": "a",
         "size_width": 100, "size_height": 40},
    ])
    plain = client.get("/api/screen/panel/image.png")
    boxed = client.get("/api/screen/panel/image.png", params={"boxes": "true"})

    assert boxed.status_code == 200
    assert boxed.content != plain.content, "outlines should actually be drawn"
    assert boxed.headers["cache-control"] == "no-store"
    assert "etag" not in boxed.headers, "an uncached view must not claim a version"

    # the cached image is unchanged and still box-free
    again = client.get("/api/screen/panel/image.png")
    assert again.content == plain.content
    assert sorted(p.name for p in (paths.image_dir / "panel").iterdir()) == \
        ["bwr.png", "metadata.json", "rgb.png"]


def test_boxes_respects_the_screen_palette_and_raw(client, paths):
    _write_screen(paths, "panel", color_model="bwr")
    boxed = client.get("/api/screen/panel/image.png", params={"boxes": "true"})
    assert Image.open(io.BytesIO(boxed.content)).mode == "P"

    boxed_raw = client.get("/api/screen/panel/image.png", params={"boxes": "true", "raw": "true"})
    assert Image.open(io.BytesIO(boxed_raw.content)).mode == "RGB"


def test_poll_cycle_uses_the_quantized_etag(client, paths):
    _write_screen(paths, "panel", color_model="bwr")
    etag = client.get("/api/screen/panel/image.png").headers["etag"]
    again = client.get("/api/screen/panel/image.png", headers={"If-None-Match": etag})
    assert again.status_code == 304


def test_editing_the_root_palette_re_renders_and_changes_the_etag(client, paths):
    """color_models.json is the one thing a screen references rather than
    contains, so editing it has to invalidate the rendered image."""
    paths.color_model_file.write_text(json.dumps([
        {"id": "duo", "name": "Black on white", "palette": [[0, 0, 0], [255, 255, 255]]},
    ]))
    _write_screen(paths, "panel", color_model="duo")
    first = client.get("/api/screen/panel/image.png").headers["etag"]

    paths.color_model_file.write_text(json.dumps([
        {"id": "duo", "name": "Black on red", "palette": [[0, 0, 0], [255, 0, 0]]},
    ]))
    stat = paths.color_model_file.stat()
    os.utime(paths.color_model_file, (stat.st_atime, stat.st_mtime + 10))

    second = client.get("/api/screen/panel/image.png")
    assert second.headers["etag"] != first
    assert second.status_code == 200
