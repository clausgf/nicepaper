import asyncio
import json
import uuid

from extensions.epaper.core.screen import get_screen_by_id
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


def test_alias_resolves_to_target_screen(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    screen_id = f"aliastarget-{uuid.uuid4().hex[:8]}"
    alias = f"alias-{uuid.uuid4().hex[:8]}"
    screen_file = paths.screen_dir / f"{screen_id}.json"
    _write_screen(screen_file)
    paths.alias_file.write_text(json.dumps({alias: screen_id}))

    by_alias = asyncio.run(get_screen_by_id(paths, alias))
    by_id = asyncio.run(get_screen_by_id(paths, screen_id))
    assert by_alias is not None
    assert by_alias is by_id, "alias and target id should share the same cached screen"
    assert by_alias.id == screen_id


def test_unknown_alias_file_is_ignored(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    assert asyncio.run(get_screen_by_id(paths, "does-not-exist")) is None


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
