"""
The display/palette catalogs: what ships with the package, and how a
per-root file extends it.
"""
import json

from extensions.epaper import catalog
from extensions.epaper.paths import EpaperPaths


def test_builtin_displays_are_complete():
    displays = catalog.get_displays()
    assert displays, "the package must ship a display catalog"
    color_model_ids = set(catalog.get_color_models())
    for display in displays.values():
        assert display.width > 0 and display.height > 0
        assert display.color_model in color_model_ids, \
            f"{display.id} references unknown palette {display.color_model}"


def test_builtin_color_models_have_palettes():
    color_models = catalog.get_color_models()
    assert {"bw", "bwr", "c7", "e6"} <= set(color_models)
    for color_model in color_models.values():
        assert len(color_model.palette) >= 2
        assert all(len(color) == 3 for color in color_model.palette)


def test_unknown_and_empty_ids_resolve_to_none():
    assert catalog.get_display("no-such-panel") is None
    assert catalog.get_display(None) is None
    assert catalog.get_color_model("no-such-palette") is None
    assert catalog.get_color_model("") is None


def test_root_file_adds_and_overrides_entries(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    builtin = catalog.get_displays()
    overridden_id = next(iter(builtin))
    paths.display_file.write_text(json.dumps([
        {"id": "my-panel", "name": "Homebrew", "width": 111, "height": 222, "color_model": "bw"},
        {"id": overridden_id, "name": "Corrected", "width": 333, "height": 444, "color_model": "bw"},
    ]))

    displays = catalog.get_displays(paths)
    assert displays["my-panel"].width == 111, "a root entry should be added"
    assert displays[overridden_id].name == "Corrected", "a root entry should override the built-in one"
    assert catalog.get_displays()[overridden_id].name == builtin[overridden_id].name, \
        "the built-in catalog must stay untouched for other roots"


def test_root_color_models_extend_the_builtin_ones(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    paths.color_model_file.write_text(json.dumps([
        {"id": "bwg", "name": "Black/Green on white",
         "palette": [[0, 0, 0], [255, 255, 255], [0, 255, 0]]},
    ]))

    assert catalog.get_color_model("bwg", paths).palette[2] == (0, 255, 0)
    assert catalog.get_color_model("bw", paths) is not None, "built-ins stay available"
    assert catalog.get_color_model("bwg") is None, "without a root, only built-ins exist"


def test_unparsable_root_file_falls_back_to_the_builtin_catalog(tmp_path):
    """A typo in an optional extra catalog must not take every screen down
    with it -- the built-in entries have to survive it."""
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    paths.display_file.write_text("{ this is not valid json")

    assert catalog.get_displays(paths) == catalog.get_displays()


def test_root_file_is_reread_after_it_changes(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    entry = {"id": "my-panel", "name": "Homebrew", "width": 111, "height": 222, "color_model": "bw"}
    paths.display_file.write_text(json.dumps([entry]))
    assert catalog.get_displays(paths)["my-panel"].width == 111

    entry["width"] = 999
    paths.display_file.write_text(json.dumps([entry]))
    # mtime may not move on a coarse-grained filesystem within one test
    stat = paths.display_file.stat()
    import os
    os.utime(paths.display_file, (stat.st_atime, stat.st_mtime + 10))

    assert catalog.get_displays(paths)["my-panel"].width == 999
