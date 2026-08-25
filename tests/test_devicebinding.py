import datetime
import json

from extensions.epaper.devicebinding.backend import (
    devices_in_room, get_device_binding, get_device_bindings, resolve_screen_and_room,
    resolve_screen_id, set_device_binding,
)
from extensions.epaper.devicebinding.models import DeviceBinding
from extensions.epaper.devicebinding.snapshot import (
    device_snapshot_png_path, read_device_snapshot, save_device_snapshot,
)
from extensions.epaper.paths import EpaperPaths


def _paths(tmp_path) -> EpaperPaths:
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    return paths


def test_device_binding_defaults_to_empty():
    b = DeviceBinding()
    assert b.room_id is None and b.screen_id is None


def test_set_binding_creates_updates_and_removes(tmp_path):
    paths = _paths(tmp_path)

    # create with a screen only
    set_device_binding(paths, "d1", screen_id="hallway")
    assert get_device_binding(paths, "d1") == DeviceBinding(screen_id="hallway")

    # a second device must not clobber the first
    set_device_binding(paths, "d2", screen_id="kitchen")
    assert set(get_device_bindings(paths)) == {"d1", "d2"}

    # room_id is left unchanged when only screen_id is passed (partial update)
    set_device_binding(paths, "d1", room_id="a-101")
    set_device_binding(paths, "d1", screen_id="foyer")
    assert get_device_binding(paths, "d1") == DeviceBinding(room_id="a-101", screen_id="foyer")

    # clearing a field passes None; the entry survives while the other is set
    set_device_binding(paths, "d1", screen_id=None)
    assert get_device_binding(paths, "d1") == DeviceBinding(room_id="a-101")

    # once both are empty the entry is dropped entirely
    set_device_binding(paths, "d1", room_id=None)
    assert set(get_device_bindings(paths)) == {"d2"}


def test_missing_binding_is_empty(tmp_path):
    paths = _paths(tmp_path)
    assert get_device_bindings(paths) == {}
    assert get_device_binding(paths, "nope") == DeviceBinding()


def test_resolve_screen_id_passthrough_and_binding(tmp_path):
    paths = _paths(tmp_path)
    # no binding -> a real screen id passes straight through
    assert resolve_screen_id(paths, "screen-x") == "screen-x"
    # a device with a screen resolves to it
    set_device_binding(paths, "dev", screen_id="screen-x")
    assert resolve_screen_id(paths, "dev") == "screen-x"
    # a device bound to a room but no screen falls back to the given id
    set_device_binding(paths, "roomonly", room_id="a-101")
    assert resolve_screen_id(paths, "roomonly") == "roomonly"


def test_devices_in_room_is_the_reverse_lookup(tmp_path):
    paths = _paths(tmp_path)
    set_device_binding(paths, "d-b", room_id="a-101", screen_id="s")
    set_device_binding(paths, "d-a", room_id="a-101")
    set_device_binding(paths, "d-c", room_id="b-201")
    assert devices_in_room(paths, "a-101") == ["d-a", "d-b"]  # sorted
    assert devices_in_room(paths, "b-201") == ["d-c"]
    assert devices_in_room(paths, "nowhere") == []


def test_legacy_aliases_are_migrated_on_first_read(tmp_path):
    paths = _paths(tmp_path)
    # the old bare aliases.json: device name -> screen id
    (paths.root / "aliases.json").write_text(json.dumps({"d1": "hallway", "d2": "kitchen"}))

    bindings = get_device_bindings(paths)
    assert bindings == {"d1": DeviceBinding(screen_id="hallway"),
                        "d2": DeviceBinding(screen_id="kitchen")}
    # migration is persisted, so it does not depend on the legacy file staying
    assert paths.device_bindings_file.exists()
    (paths.root / "aliases.json").unlink()
    assert resolve_screen_id(paths, "d1") == "hallway"


def test_existing_bindings_file_wins_over_legacy_aliases(tmp_path):
    paths = _paths(tmp_path)
    # both present: the new file is authoritative, no migration overwrites it
    set_device_binding(paths, "d1", screen_id="new")
    (paths.root / "aliases.json").write_text(json.dumps({"d1": "old"}))
    assert resolve_screen_id(paths, "d1") == "new"


def test_panel_type_id_is_independent_of_screen_and_room(tmp_path):
    paths = _paths(tmp_path)
    set_device_binding(paths, "d1", panel_type_id="waveshare_7in5_v2")
    assert get_device_binding(paths, "d1") == DeviceBinding(panel_type_id="waveshare_7in5_v2")

    set_device_binding(paths, "d1", screen_id="hallway")
    assert get_device_binding(paths, "d1") == DeviceBinding(
        panel_type_id="waveshare_7in5_v2", screen_id="hallway")

    # dropped only once all three fields are empty
    set_device_binding(paths, "d1", screen_id=None)
    assert get_device_binding(paths, "d1") == DeviceBinding(panel_type_id="waveshare_7in5_v2")
    set_device_binding(paths, "d1", panel_type_id=None)
    assert set(get_device_bindings(paths)) == set()


def test_resolve_screen_and_room(tmp_path):
    paths = _paths(tmp_path)
    # a literal screen id (no binding) passes through with no room
    assert resolve_screen_and_room(paths, "screen-x") == ("screen-x", None)

    # a device bound to a screen and a room resolves both
    set_device_binding(paths, "dev", screen_id="screen-x", room_id="a-101")
    assert resolve_screen_and_room(paths, "dev") == ("screen-x", "a-101")

    # a device bound to a room only falls back to its own name as the screen id
    set_device_binding(paths, "roomonly", room_id="a-101")
    assert resolve_screen_and_room(paths, "roomonly") == ("roomonly", "a-101")


def test_device_snapshot_missing_reads_as_none(tmp_path):
    paths = _paths(tmp_path)
    assert read_device_snapshot(paths, "dev") is None


def test_device_snapshot_save_and_read_round_trip(tmp_path):
    paths = _paths(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"first-image-bytes")

    save_device_snapshot(paths, "dev", source)

    snapshot = read_device_snapshot(paths, "dev")
    assert snapshot is not None
    now = datetime.datetime.now(datetime.timezone.utc)
    assert (now - snapshot.fetched_at).total_seconds() < 5
    assert device_snapshot_png_path(paths, "dev").read_bytes() == b"first-image-bytes"


def test_device_snapshot_save_overwrites_the_previous_one(tmp_path):
    paths = _paths(tmp_path)
    source = tmp_path / "source.png"

    source.write_bytes(b"first")
    save_device_snapshot(paths, "dev", source)
    first = read_device_snapshot(paths, "dev")

    source.write_bytes(b"second")
    save_device_snapshot(paths, "dev", source)
    second = read_device_snapshot(paths, "dev")

    assert device_snapshot_png_path(paths, "dev").read_bytes() == b"second"
    assert second is not None and first is not None
    assert second.fetched_at >= first.fetched_at


def test_device_snapshots_are_independent_per_device(tmp_path):
    paths = _paths(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"data")

    save_device_snapshot(paths, "dev-a", source)
    assert read_device_snapshot(paths, "dev-b") is None
    assert read_device_snapshot(paths, "dev-a") is not None
