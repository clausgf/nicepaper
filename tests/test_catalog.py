"""
The panel-type/palette catalogs: what ships with the package, and how a
per-root file extends it.
"""
import json

from extensions.epaper.catalog import backend as catalog
from extensions.epaper.catalog.models import Palette
from extensions.epaper.paths import EpaperPaths


def test_builtin_displays_are_complete():
    displays = catalog.get_panel_types()
    assert displays, "the package must ship a display catalog"
    palette_ids = set(catalog.get_palettes())
    for display in displays.values():
        assert display.width > 0 and display.height > 0
        assert display.palette_id in palette_ids, \
            f"{display.id} references unknown palette {display.palette_id}"


def test_builtin_palettes_have_colors():
    palettes = catalog.get_palettes()
    assert {"bw", "bwr", "c7", "e6"} <= set(palettes)
    for palette in palettes.values():
        assert len(palette.palette) >= 2
        assert all(len(color) == 3 for color in palette.palette)


def test_unknown_and_empty_ids_resolve_to_none():
    assert catalog.get_panel_type("no-such-panel") is None
    assert catalog.get_panel_type(None) is None
    assert catalog.get_palette("no-such-palette") is None
    assert catalog.get_palette("") is None


def test_panel_type_label_leads_with_panel_id():
    """A select's value is already the catalog id -- the label needs
    panel_id (the manufacturer's own designation, shared by rebrands of the
    same hardware) since name alone can't distinguish those."""
    panel_type = catalog.get_panel_types()["waveshare_7in5_v2"]
    assert panel_type.panel_id  # otherwise this test doesn't exercise the interesting branch
    assert catalog.panel_type_label(panel_type) == f"{panel_type.panel_id} {panel_type.name}"


def test_panel_type_label_falls_back_to_name_without_a_panel_id():
    from extensions.epaper.catalog.models import PanelTypeModel
    panel_type = PanelTypeModel(id="x", name="Custom panel", width=1, height=1)
    assert catalog.panel_type_label(panel_type) == "Custom panel"


def test_root_file_adds_and_overrides_entries(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    builtin = catalog.get_panel_types()
    overridden_id = next(iter(builtin))
    paths.panel_types_file.write_text(json.dumps([
        {"id": "my-panel", "name": "Homebrew", "width": 111, "height": 222, "palette_id": "bw"},
        {"id": overridden_id, "name": "Corrected", "width": 333, "height": 444, "palette_id": "bw"},
    ]))

    displays = catalog.get_panel_types(paths)
    assert displays["my-panel"].width == 111, "a root entry should be added"
    assert displays[overridden_id].name == "Corrected", "a root entry should override the built-in one"
    assert catalog.get_panel_types()[overridden_id].name == builtin[overridden_id].name, \
        "the built-in catalog must stay untouched for other roots"


def test_root_palettes_extend_the_builtin_ones(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    paths.palettes_file.write_text(json.dumps([
        {"id": "bwg", "name": "Black/Green on white",
         "palette": [[0, 0, 0], [255, 255, 255], [0, 255, 0]]},
    ]))

    assert catalog.get_palette("bwg", paths).palette[2] == (0, 255, 0)
    assert catalog.get_palette("bw", paths) is not None, "built-ins stay available"
    assert catalog.get_palette("bwg") is None, "without a root, only built-ins exist"


def test_unparsable_root_file_falls_back_to_the_builtin_catalog(tmp_path):
    """A typo in an optional extra catalog must not take every screen down
    with it -- the built-in entries have to survive it."""
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    paths.panel_types_file.write_text("{ this is not valid json")

    assert catalog.get_panel_types(paths) == catalog.get_panel_types()


def test_root_file_is_reread_after_it_changes(tmp_path):
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    entry = {"id": "my-panel", "name": "Homebrew", "width": 111, "height": 222, "palette_id": "bw"}
    paths.panel_types_file.write_text(json.dumps([entry]))
    assert catalog.get_panel_types(paths)["my-panel"].width == 111

    entry["width"] = 999
    paths.panel_types_file.write_text(json.dumps([entry]))
    # mtime may not move on a coarse-grained filesystem within one test
    stat = paths.panel_types_file.stat()
    import os
    os.utime(paths.panel_types_file, (stat.st_atime, stat.st_mtime + 10))

    assert catalog.get_panel_types(paths)["my-panel"].width == 999


_BWR = Palette(id="bwr", name="test", palette=[(0, 0, 0), (255, 255, 255), (255, 0, 0)])


def test_nearest_palette_color_snaps_to_closest_member():
    assert catalog.nearest_palette_color((10, 10, 10), _BWR) == (0, 0, 0)
    assert catalog.nearest_palette_color((250, 20, 20), _BWR) == (255, 0, 0)


def test_nearest_palette_color_excludes_white_by_default():
    # closer to white than to black, but white is excluded -> falls back to
    # whichever non-white member is actually nearest
    assert catalog.nearest_palette_color((240, 240, 240), _BWR) == (255, 0, 0) \
        or catalog.nearest_palette_color((240, 240, 240), _BWR) == (0, 0, 0)
    assert catalog.nearest_palette_color((240, 240, 240), _BWR) != (255, 255, 255)


def test_nearest_palette_color_can_include_white():
    assert catalog.nearest_palette_color((240, 240, 240), _BWR, exclude_white=False) == (255, 255, 255)


def test_nearest_palette_color_falls_back_to_white_if_thats_all_there_is():
    white_only = Palette(id="w", name="test", palette=[(255, 255, 255)])
    assert catalog.nearest_palette_color((0, 0, 0), white_only) == (255, 255, 255)
