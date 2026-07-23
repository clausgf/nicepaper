import asyncio
import io

from PIL import Image

from extensions.epaper.core.datasources.image import _cache_path, clear_cache, get_image
from extensions.epaper.core.widgets.image import target_size
from extensions.epaper.models.screenmodel import ImageWidgetModel
from extensions.epaper.paths import EpaperPaths


def _png_bytes(color=(255, 0, 0), size=(4, 4)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _paths(tmp_path) -> EpaperPaths:
    paths = EpaperPaths(root=tmp_path / "root", project_root=tmp_path / "project")
    paths.ensure_dirs()
    paths.asset_dir.mkdir(parents=True, exist_ok=True)
    return paths


def _file_config(**kwargs) -> ImageWidgetModel:
    return ImageWidgetModel(position_x=0, position_y=0, source_type="file", **kwargs)


def test_target_size_scaling_rules():
    assert target_size((200, 100), 50, 25) == (50, 25)     # both -> exact
    assert target_size((200, 100), 50, None) == (50, 25)   # width only -> keep aspect
    assert target_size((200, 100), None, 50) == (100, 50)  # height only -> keep aspect
    assert target_size((200, 100), 0, 0) == (200, 100)     # 0/0 (cleared) -> natural
    assert target_size((200, 100), None, None) == (200, 100)


def test_get_image_from_project_file(tmp_path):
    paths = _paths(tmp_path)
    (paths.asset_dir / "pic.png").write_bytes(_png_bytes(size=(6, 3)))
    img = asyncio.run(get_image(paths, _file_config(file="pic.png")))
    assert img is not None and img.size == (6, 3)


def test_get_image_missing_file_returns_none(tmp_path):
    paths = _paths(tmp_path)
    assert asyncio.run(get_image(paths, _file_config(file="nope.png"))) is None


def test_get_image_rejects_path_traversal(tmp_path):
    paths = _paths(tmp_path)
    (tmp_path / "secret.png").write_bytes(_png_bytes())  # outside the asset dir
    assert asyncio.run(get_image(paths, _file_config(file="../secret.png"))) is None


def test_get_image_caches_once_and_reload_now_clears(tmp_path):
    paths = _paths(tmp_path)
    f = paths.asset_dir / "pic.png"
    f.write_bytes(_png_bytes((255, 0, 0)))
    config = _file_config(file="pic.png")  # reload_each_time defaults False

    first = asyncio.run(get_image(paths, config))
    assert first.getpixel((0, 0)) == (255, 0, 0)
    assert _cache_path(paths, config).is_file()

    f.write_bytes(_png_bytes((0, 0, 255)))  # source changes...
    cached = asyncio.run(get_image(paths, config))
    assert cached.getpixel((0, 0)) == (255, 0, 0)  # ...but cache still serves the old image

    clear_cache(paths, config)  # 'Reload now'
    reloaded = asyncio.run(get_image(paths, config))
    assert reloaded.getpixel((0, 0)) == (0, 0, 255)


def test_reload_each_time_never_caches(tmp_path):
    paths = _paths(tmp_path)
    f = paths.asset_dir / "pic.png"
    f.write_bytes(_png_bytes((255, 0, 0)))
    config = _file_config(file="pic.png", reload_each_time=True)

    asyncio.run(get_image(paths, config))
    assert not _cache_path(paths, config).exists()

    f.write_bytes(_png_bytes((0, 0, 255)))
    assert asyncio.run(get_image(paths, config)).getpixel((0, 0)) == (0, 0, 255)
