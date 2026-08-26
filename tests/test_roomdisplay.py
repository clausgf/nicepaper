import datetime
import json
import types

import extensions.epaper.display.backend as rd
from extensions.epaper.devicebinding.backend import get_device_binding, set_device_binding
from extensions.epaper.room.backend import create_room, room_adapter
from extensions.epaper.paths import EpaperPaths

NOW = datetime.datetime.now(datetime.timezone.utc)


def _paths(tmp_path) -> EpaperPaths:
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    return paths


def _fake_devices(*devices):
    return lambda project: list(devices)


def _dev(name, last_seen=NOW):
    return types.SimpleNamespace(name=name, last_seen_at=last_seen)


def test_no_devices_outside_nice4iot(tmp_path):
    # default _project_devices can't import app.* here -> empty, grid degrades
    assert rd.display_rows(_paths(tmp_path), "proj") == []


def test_display_rows_join_room_and_online(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room = create_room(paths)
    room.building, room.floor, room.room_number = "B", "1", "A-101"
    room_adapter(paths, room.id).save(room)
    set_device_binding(paths, "d-online", room_id=room.id, screen_id="scr")
    set_device_binding(paths, "d-stale", room_id=room.id)

    monkeypatch.setattr(rd, "_project_devices", _fake_devices(
        _dev("d-online", NOW),
        _dev("d-stale", NOW - datetime.timedelta(hours=1)),
        _dev("d-unbound", None),
    ))

    rows = {r.device_name: r for r in rd.display_rows(paths, "proj")}
    assert set(rows) == {"d-online", "d-stale", "d-unbound"}
    assert rows["d-online"].online is True and rows["d-stale"].online is False
    assert rows["d-unbound"].online is False  # last_seen None
    # room columns come from the device's own bound room
    assert (rows["d-online"].building, rows["d-online"].room_number) == ("B", "A-101")
    assert rows["d-online"].screen_id == "scr"
    assert rows["d-unbound"].building == ""  # not in a room
    # unavailable columns stay empty
    assert rows["d-online"].rssi is None and rows["d-online"].battery_voltage is None


def test_display_rows_read_telemetry_and_alarms_from_runtime(tmp_path, monkeypatch):
    """rssi/battery_voltage come from _device_runtime (nice4iot's DeviceRuntime),
    alarm_count/firmware_version straight off the device object."""
    paths = _paths(tmp_path)
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(
        types.SimpleNamespace(name="d", last_seen_at=NOW, firmware_version="1.4.2",
                              active_alarms=2),
    ))
    monkeypatch.setattr(rd, "_device_runtime", lambda project, name:
                        types.SimpleNamespace(rssi=-65.7, battery_voltage=3.81))

    row = rd.display_rows(paths, "proj")[0]
    assert row.firmware_version == "1.4.2"
    assert row.alarm_count == 2
    assert row.rssi == -66  # rounded
    assert row.battery_voltage == 3.81


def test_display_rows_treats_nonfinite_telemetry_as_no_reading(tmp_path, monkeypatch):
    """A NaN/inf sample (a bad sensor read) must not reach round()/the UI's
    bar-index math as a real value -- round(nan) raises ValueError, which
    would otherwise take down the whole row (rssi) or crash a single icon's
    render (battery_voltage, display/simplified_ui.py's _battery_icon)."""
    paths = _paths(tmp_path)
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(types.SimpleNamespace(name="d", last_seen_at=NOW)))
    monkeypatch.setattr(rd, "_device_runtime", lambda project, name:
                        types.SimpleNamespace(rssi=float("nan"), battery_voltage=float("inf")))

    row = rd.display_rows(paths, "proj")[0]
    assert row.rssi is None
    assert row.battery_voltage is None


def test_display_rows_room_filter(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room = create_room(paths)
    set_device_binding(paths, "in-room", room_id=room.id)
    set_device_binding(paths, "other", room_id="somewhere-else")
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(_dev("in-room"), _dev("other")))

    names = [r.device_name for r in rd.display_rows(paths, "proj", room_id=room.id)]
    assert names == ["in-room"]


def test_assignable_devices_excludes_this_room(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room = create_room(paths)
    set_device_binding(paths, "here", room_id=room.id)
    monkeypatch.setattr(rd, "_project_devices",
                        _fake_devices(_dev("here"), _dev("free"), _dev("elsewhere")))
    set_device_binding(paths, "elsewhere", room_id="other-room")
    assert rd.assignable_devices(paths, "proj", room.id) == ["elsewhere", "free"]


def test_adapter_update_writes_only_screen_id(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room = create_room(paths)
    set_device_binding(paths, "d", room_id=room.id)
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(_dev("d")))

    adapter = rd.RoomDisplaysAdapter(paths, "proj", room.id)
    row = adapter.read("d")
    row.screen_id = "scr"
    adapter.update(row)
    binding = get_device_binding(paths, "d")
    assert binding.screen_id == "scr" and binding.room_id == room.id  # room kept

    # clearing the screen ('') unassigns the screen, keeps the room
    row.screen_id = ""
    adapter.update(row)
    assert get_device_binding(paths, "d").screen_id is None


def test_adapter_delete_unassigns_from_room(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room = create_room(paths)
    set_device_binding(paths, "d", room_id=room.id, screen_id="scr")
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(_dev("d")))

    rd.RoomDisplaysAdapter(paths, "proj", room.id).delete("d")
    binding = get_device_binding(paths, "d")
    assert binding.room_id is None and binding.screen_id == "scr"  # device + screen kept


def test_project_device_names_lists_every_device_unfiltered(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room = create_room(paths)
    set_device_binding(paths, "in-room", room_id=room.id)
    monkeypatch.setattr(rd, "_project_devices",
                        _fake_devices(_dev("in-room"), _dev("elsewhere"), _dev("unbound")))
    # unlike assignable_devices(), a device already in *this* room is included too
    assert rd.project_device_names("proj") == ["elsewhere", "in-room", "unbound"]


def test_adapter_rename_moves_room_and_screen_to_the_new_device(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room = create_room(paths)
    set_device_binding(paths, "old", room_id=room.id, screen_id="scr")
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(_dev("old"), _dev("new")))

    adapter = rd.RoomDisplaysAdapter(paths, "proj", room.id)
    assert adapter.rename("old", "new") == "new"

    new_binding = get_device_binding(paths, "new")
    assert (new_binding.room_id, new_binding.screen_id) == (room.id, "scr")
    old_binding = get_device_binding(paths, "old")
    assert old_binding.room_id is None  # unbound from the room...
    assert old_binding.screen_id == "scr"  # ...but its own screen is untouched


def test_adapter_rename_to_the_same_device_is_a_noop(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room = create_room(paths)
    set_device_binding(paths, "d", room_id=room.id, screen_id="scr")
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(_dev("d")))

    adapter = rd.RoomDisplaysAdapter(paths, "proj", room.id)
    assert adapter.rename("d", "d") == "d"
    binding = get_device_binding(paths, "d")
    assert (binding.room_id, binding.screen_id) == (room.id, "scr")


def test_adapter_rename_moves_a_device_from_another_room(tmp_path, monkeypatch):
    """A device already in a different room is moved here, same as
    assignable_devices()/create() already allow."""
    paths = _paths(tmp_path)
    room = create_room(paths)
    set_device_binding(paths, "old", room_id=room.id, screen_id="scr")
    set_device_binding(paths, "elsewhere", room_id="other-room")
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(_dev("old"), _dev("elsewhere")))

    adapter = rd.RoomDisplaysAdapter(paths, "proj", room.id)
    assert adapter.rename("old", "elsewhere") == "elsewhere"
    moved = get_device_binding(paths, "elsewhere")
    assert (moved.room_id, moved.screen_id) == (room.id, "scr")


def test_available_screen_ids_matches_real_screen_by_resolution_and_palette(tmp_path):
    paths = _paths(tmp_path)
    (paths.screen_dir / "matching.json").write_text(json.dumps({
        "width": 400, "height": 300, "palette_id": "bw", "widgets": [],
    }))
    (paths.screen_dir / "mismatched.json").write_text(json.dumps({
        "width": 800, "height": 480, "palette_id": "bw", "widgets": [],
    }))
    set_device_binding(paths, "d1", panel_type_id="waveshare_4in2")  # 400x300 bw

    ids = rd.available_screen_ids(paths, "d1")
    assert "matching" in ids
    assert "mismatched" not in ids


def test_available_screen_ids_keeps_a_dangling_assignment_visible(tmp_path):
    paths = _paths(tmp_path)
    set_device_binding(paths, "d1", panel_type_id="waveshare_4in2", screen_id="does-not-match")
    (paths.screen_dir / "does-not-match.json").write_text(json.dumps({
        "width": 800, "height": 480, "widgets": [],
    }))

    ids = rd.available_screen_ids(paths, "d1")
    assert "does-not-match" in ids  # kept visible even though it doesn't match its panel type


def test_available_screen_ids_unfiltered_without_a_panel_type(tmp_path):
    paths = _paths(tmp_path)
    (paths.screen_dir / "any.json").write_text(json.dumps({
        "width": 800, "height": 480, "widgets": [],
    }))
    ids = rd.available_screen_ids(paths, "no-binding-device")
    assert "any" in ids
    assert any(i.startswith("__roomcalendar_") for i in ids), \
        "synthetic Room Calendar templates should always be offered"
