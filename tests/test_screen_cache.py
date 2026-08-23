import asyncio
import json
import uuid

from extensions.epaper.catalog.backend import get_panel_type
from extensions.epaper.devicebinding.backend import set_device_binding
from extensions.epaper.room.backend import create_room
from extensions.epaper.screen.backend import (
    get_screen_by_id, screens_matching_panel_type, synthetic_roomcalendar_screens,
)
from extensions.epaper.paths import EpaperPaths


SCREEN = {
    "width": 100,
    "height": 50,
    "widgets": [
        {"widget_type": "Text", "position_x": 0, "position_y": 0, "size_width": 100, "size_height": 20, "text": "cache test"}
    ],
}


def _write_screen(path):
    with open(path, "w") as f:
        json.dump(SCREEN, f)


def test_screen_cache_reuses_and_invalidates(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    screen_id = f"cachetest-{uuid.uuid4().hex[:8]}"
    screen_file = paths.screen_dir / f"{screen_id}.json"
    _write_screen(screen_file)

    first = asyncio.run(get_screen_by_id(paths, screen_id))
    second = asyncio.run(get_screen_by_id(paths, screen_id))
    assert first is not None
    assert second is first, "unchanged screen should be served from cache"

    # bump the file mtime -> cache must reload
    import os
    stat = os.stat(screen_file)
    os.utime(screen_file, (stat.st_atime, stat.st_mtime + 10))
    third = asyncio.run(get_screen_by_id(paths, screen_id))
    assert third is not None
    assert third is not first, "modified screen file should invalidate the cache"

    # removing the file drops the cache entry
    os.remove(screen_file)
    assert asyncio.run(get_screen_by_id(paths, screen_id)) is None


def test_device_binding_resolves_to_target_screen(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    screen_id = f"bindingtarget-{uuid.uuid4().hex[:8]}"
    device = f"device-{uuid.uuid4().hex[:8]}"
    _write_screen(paths.screen_dir / f"{screen_id}.json")
    set_device_binding(paths, device, screen_id=screen_id)

    by_device = asyncio.run(get_screen_by_id(paths, device))
    by_id = asyncio.run(get_screen_by_id(paths, screen_id))
    assert by_device is not None
    assert by_device is by_id, "device name and target id should share the same cached screen"
    assert by_device.id == screen_id


def test_unknown_id_is_ignored(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    assert asyncio.run(get_screen_by_id(paths, "does-not-exist")) is None


def test_device_binding_resolves_through_get_screen_by_id(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    screen_id = f"devicetarget-{uuid.uuid4().hex[:8]}"
    _write_screen(paths.screen_dir / f"{screen_id}.json")

    set_device_binding(paths, "my-device", screen_id=screen_id)
    screen = asyncio.run(get_screen_by_id(paths, "my-device"))
    assert screen is not None
    assert screen.id == screen_id


def test_screen_cache_distinguishes_same_id_under_different_roots(tmp_path):
    """
    Two different roots (e.g. two nice4iot projects) with a screen file of
    the same id must not collide in the module-level cache.
    """
    paths_a = EpaperPaths(root=tmp_path / "a")
    paths_b = EpaperPaths(root=tmp_path / "b")
    paths_a.ensure_dirs()
    paths_b.ensure_dirs()
    _write_screen(paths_a.screen_dir / "shared.json")
    _write_screen(paths_b.screen_dir / "shared.json")

    screen_a = asyncio.run(get_screen_by_id(paths_a, "shared"))
    screen_b = asyncio.run(get_screen_by_id(paths_b, "shared"))
    assert screen_a is not None and screen_b is not None
    assert screen_a is not screen_b
    assert screen_a.paths.root == paths_a.root
    assert screen_b.paths.root == paths_b.root


def test_screen_cache_separates_by_room(tmp_path):
    """Two devices bound to the same screen but different rooms must not
    share a cached Screen instance (or its rendered image) -- needed for a
    screen shared across rooms (e.g. an auto-generated RoomCalendar
    template) to render each device's own room."""
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    screen_id = f"roomaware-{uuid.uuid4().hex[:8]}"
    _write_screen(paths.screen_dir / f"{screen_id}.json")
    room_a = create_room(paths)
    room_b = create_room(paths)
    set_device_binding(paths, "device-a", screen_id=screen_id, room_id=room_a.id)
    set_device_binding(paths, "device-b", screen_id=screen_id, room_id=room_b.id)

    screen_a = asyncio.run(get_screen_by_id(paths, "device-a"))
    screen_b = asyncio.run(get_screen_by_id(paths, "device-b"))
    assert screen_a is not None and screen_b is not None
    assert screen_a is not screen_b
    assert screen_a.id == screen_b.id == screen_id
    assert screen_a.room.id == room_a.id
    assert screen_b.room.id == room_b.id
    assert screen_a.image_cache.image_dir != screen_b.image_cache.image_dir


def test_synthetic_roomcalendar_template_renders(tmp_path):
    """An auto-generated 'Room Calendar WxH palette' id resolves to a real
    Screen built from the panel-type catalog, not a file on disk."""
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    templates = synthetic_roomcalendar_screens(paths)
    assert templates, "the built-in panel catalog should yield at least one template"
    template_id = next(iter(templates))
    assert not (paths.screen_dir / f"{template_id}.json").exists()

    screen = asyncio.run(get_screen_by_id(paths, template_id))
    assert screen is not None
    assert screen.id == template_id
    assert screen.config.widgets[0].widget_type == "RoomCalendar"

    cached = asyncio.run(get_screen_by_id(paths, template_id))
    assert cached is screen, "unchanged catalog should be served from cache"


def test_screens_matching_panel_type_includes_the_synthetic_template(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    panel_type = get_panel_type("waveshare_7in5_v2", paths)  # 800x480 bw
    assert panel_type is not None

    matches = screens_matching_panel_type(paths, panel_type)
    template_id = f"__roomcalendar_{panel_type.width}x{panel_type.height}_{panel_type.palette_id}"
    assert template_id in matches
