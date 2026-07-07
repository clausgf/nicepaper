import asyncio
import json
import os
import shutil
import uuid

from app.config import app_config
from app.core.screen import get_screen_by_id


SCREEN = {
    "size": [100, 50],
    "widgets": [
        {"widget_type": "Text", "position": [0, 0], "size": [100, 20], "text": "cache test"}
    ],
}


def _write_screen(path):
    with open(path, "w") as f:
        json.dump(SCREEN, f)


def test_screen_cache_reuses_and_invalidates(tmp_path):
    screen_id = f"cachetest-{uuid.uuid4().hex[:8]}"
    screen_file = os.path.join(app_config.screen_dir, f"{screen_id}.json")
    _write_screen(screen_file)
    try:
        first = asyncio.run(get_screen_by_id(screen_id))
        second = asyncio.run(get_screen_by_id(screen_id))
        assert first is not None
        assert second is first, "unchanged screen should be served from cache"

        # bump the file mtime -> cache must reload
        stat = os.stat(screen_file)
        os.utime(screen_file, (stat.st_atime, stat.st_mtime + 10))
        third = asyncio.run(get_screen_by_id(screen_id))
        assert third is not None
        assert third is not first, "modified screen file should invalidate the cache"

        # removing the file drops the cache entry
        os.remove(screen_file)
        assert asyncio.run(get_screen_by_id(screen_id)) is None
    finally:
        if os.path.exists(screen_file):
            os.remove(screen_file)
        shutil.rmtree(os.path.join(app_config.image_dir, screen_id), ignore_errors=True)


def test_alias_resolves_to_target_screen(tmp_path, monkeypatch):
    screen_id = f"aliastarget-{uuid.uuid4().hex[:8]}"
    alias = f"alias-{uuid.uuid4().hex[:8]}"
    screen_file = os.path.join(app_config.screen_dir, f"{screen_id}.json")
    _write_screen(screen_file)

    alias_file = tmp_path / "aliases.json"
    alias_file.write_text(json.dumps({alias: screen_id}))
    monkeypatch.setattr(app_config, "alias_file", str(alias_file))

    try:
        by_alias = asyncio.run(get_screen_by_id(alias))
        by_id = asyncio.run(get_screen_by_id(screen_id))
        assert by_alias is not None
        assert by_alias is by_id, "alias and target id should share the same cached screen"
        assert by_alias.id == screen_id
    finally:
        if os.path.exists(screen_file):
            os.remove(screen_file)
        shutil.rmtree(os.path.join(app_config.image_dir, screen_id), ignore_errors=True)


def test_unknown_alias_file_is_ignored(monkeypatch):
    monkeypatch.setattr(app_config, "alias_file", "/nonexistent/aliases.json")
    assert asyncio.run(get_screen_by_id("does-not-exist")) is None
