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


def test_display_rows_flags_a_deleted_room_instead_of_looking_unassigned(tmp_path, monkeypatch):
    """A device's room_id can outlive the room itself (room/backend.py's
    delete_room() leaves dangling refs visible on purpose) -- room_label must
    say so, not fall back to the same blank '' an actually-unassigned device
    would have (that would silently mask the dangling reference)."""
    paths = _paths(tmp_path)
    set_device_binding(paths, "d-orphaned", room_id="does-not-exist")
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(_dev("d-orphaned")))

    rows = {r.device_name: r for r in rd.display_rows(paths, "proj")}
    assert rows["d-orphaned"].room_label == "Room deleted ⚠"


def test_display_rows_screen_label_flags_a_missing_screen(tmp_path, monkeypatch):
    """screen_label warns when screen_id no longer names a real screen (or a
    still-valid synthetic Room Calendar template); screen_id itself must stay
    the raw value (it's the one the Screen field actually reads/writes)."""
    paths = _paths(tmp_path)
    (paths.screen_dir / "real.json").write_text(json.dumps(
        {"width": 100, "height": 100, "widgets": []}))
    set_device_binding(paths, "d-real-screen", screen_id="real")
    set_device_binding(paths, "d-gone-screen", screen_id="does-not-exist")
    set_device_binding(paths, "d-no-screen")

    monkeypatch.setattr(rd, "_project_devices", _fake_devices(
        _dev("d-real-screen"), _dev("d-gone-screen"), _dev("d-no-screen"),
    ))

    rows = {r.device_name: r for r in rd.display_rows(paths, "proj")}
    assert rows["d-real-screen"].screen_id == "real"
    assert rows["d-real-screen"].screen_label == "real"
    assert rows["d-gone-screen"].screen_label == "does-not-exist ⚠"
    assert rows["d-no-screen"].screen_id == ""
    assert rows["d-no-screen"].screen_label == "—"


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


def test_display_rows_read_panel_type_and_reported_panel(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    set_device_binding(paths, "d", panel_type_id="waveshare_7in5_v2")
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(
        types.SimpleNamespace(name="d", last_seen_at=NOW),
    ))
    monkeypatch.setattr(rd, "_device_runtime", lambda project, name:
                        types.SimpleNamespace(kind_labels={"epaper": {"panel": "GDEW075T7",
                                                                      "panels": "GDEW075T7,GDEP073E01"}}))

    row = rd.display_rows(paths, "proj")[0]
    assert row.panel_type_id == "waveshare_7in5_v2"
    assert row.reported_panel == "GDEW075T7"
    assert row.reported_panels == "GDEW075T7,GDEP073E01"
    # matches the reported panel -- no "⚠" suffix
    assert row.panel_label == 'GDEW075T7 Waveshare 7.5" V2/V3 (800x480 b/w)'


def test_display_rows_panel_label_flags_a_mismatch(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    set_device_binding(paths, "d", panel_type_id="waveshare_7in5_v2")
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(
        types.SimpleNamespace(name="d", last_seen_at=NOW),
    ))
    monkeypatch.setattr(rd, "_device_runtime", lambda project, name:
                        types.SimpleNamespace(kind_labels={"epaper": {"panel": "GDEW0583T7", "panels": ""}}))

    row = rd.display_rows(paths, "proj")[0]
    assert row.panel_label == 'GDEW075T7 Waveshare 7.5" V2/V3 (800x480 b/w) ⚠'


def test_display_rows_panel_label_placeholder_without_a_panel_type(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(_dev("d")))
    row = rd.display_rows(paths, "proj")[0]
    assert row.panel_label == "—"


def test_device_epaper_labels_outside_nice4iot(tmp_path):
    # _device_runtime can't import app.* here -> None, degrades to {}
    assert rd.device_epaper_labels("proj", "dev") == {}


def test_device_epaper_labels_reads_kind_labels(monkeypatch):
    monkeypatch.setattr(rd, "_device_runtime", lambda project, name:
                        types.SimpleNamespace(kind_labels={"epaper": {"panel": "GDEW075T7",
                                                                      "panels": "GDEW075T7,GDEP073E01"}}))
    assert rd.device_epaper_labels("proj", "dev") == {"panel": "GDEW075T7",
                                                       "panels": "GDEW075T7,GDEP073E01"}


def test_device_epaper_labels_missing_kind_is_empty(monkeypatch):
    monkeypatch.setattr(rd, "_device_runtime", lambda project, name:
                        types.SimpleNamespace(kind_labels={}))
    assert rd.device_epaper_labels("proj", "dev") == {}


def test_device_epaper_telemetry_outside_nice4iot(tmp_path):
    assert rd.device_epaper_telemetry("proj", "dev") == ({}, {}, None)


def test_device_epaper_telemetry_reads_metrics_labels_and_timestamp(monkeypatch):
    monkeypatch.setattr(rd, "_device_runtime", lambda project, name:
                        types.SimpleNamespace(
                            kind_metrics={"epaper": {"image_status": 200.0}},
                            kind_labels={"epaper": {"panel": "GDEW075T7"}},
                            kind_reported_at={"epaper": NOW}))
    metrics, labels, reported_at = rd.device_epaper_telemetry("proj", "dev")
    assert metrics == {"image_status": 200.0}
    assert labels == {"panel": "GDEW075T7"}
    assert reported_at == NOW


# ---------------------------------------------------------------------------
# panel_mismatch_hint
# ---------------------------------------------------------------------------

def _panel_types(tmp_path):
    from extensions.epaper.catalog.backend import get_panel_types
    return get_panel_types(_paths(tmp_path))


def test_panel_mismatch_hint_no_report_is_none(tmp_path):
    panel_types = _panel_types(tmp_path)
    assert rd.panel_mismatch_hint(_paths(tmp_path), panel_types, "waveshare_7in5_v2", "") is None


def test_panel_mismatch_hint_matching_selection_is_none(tmp_path):
    paths = _paths(tmp_path)
    panel_types = _panel_types(tmp_path)
    assert rd.panel_mismatch_hint(paths, panel_types, "waveshare_7in5_v2", "GDEW075T7") is None


def test_panel_mismatch_hint_mismatched_selection_warns(tmp_path):
    paths = _paths(tmp_path)
    panel_types = _panel_types(tmp_path)
    hint = rd.panel_mismatch_hint(paths, panel_types, "waveshare_7in5_v2", "GDEP073E01")
    assert hint is not None
    assert "GDEP073E01" in hint and "GDEW075T7" in hint


def test_panel_mismatch_hint_unselected_with_catalog_match(tmp_path):
    paths = _paths(tmp_path)
    panel_types = _panel_types(tmp_path)
    hint = rd.panel_mismatch_hint(paths, panel_types, None, "GDEW075T7")
    assert hint is not None
    assert "Matches:" in hint


def test_panel_mismatch_hint_unselected_without_catalog_match(tmp_path):
    paths = _paths(tmp_path)
    panel_types = _panel_types(tmp_path)
    hint = rd.panel_mismatch_hint(paths, panel_types, None, "SOME-UNKNOWN-PANEL")
    assert hint is not None
    assert "No catalog entry" in hint


# ---------------------------------------------------------------------------
# RoomDisplaysAdapter.update() persists panel_type_id
# ---------------------------------------------------------------------------

def test_adapter_update_persists_panel_type_id(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(
        types.SimpleNamespace(name="d", last_seen_at=NOW),
    ))
    adapter = rd.RoomDisplaysAdapter(paths, "proj")
    item = adapter.read("d")
    item.panel_type_id = "waveshare_7in5_v2"
    adapter.update(item)

    assert get_device_binding(paths, "d").panel_type_id == "waveshare_7in5_v2"


def test_adapter_update_screen_id_preserves_panel_type_id(tmp_path, monkeypatch):
    """A screen_id-only ModelForm autosave must not wipe an already-set
    panel_type_id (adapter.update() receives the full row, not just the
    changed field -- see RoomDisplaysAdapter.update()'s comment)."""
    paths = _paths(tmp_path)
    set_device_binding(paths, "d", panel_type_id="waveshare_7in5_v2")
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(
        types.SimpleNamespace(name="d", last_seen_at=NOW),
    ))
    adapter = rd.RoomDisplaysAdapter(paths, "proj")
    item = adapter.read("d")
    item.screen_id = "some-screen"
    adapter.update(item)

    binding = get_device_binding(paths, "d")
    assert binding.screen_id == "some-screen"
    assert binding.panel_type_id == "waveshare_7in5_v2"


def test_display_rows_reads_active_and_provisioning_from_device(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(
        types.SimpleNamespace(name="d", last_seen_at=NOW,
                              is_active=False, is_provisioning_approved=True),
    ))

    row = rd.display_rows(paths, "proj")[0]
    assert row.is_active is False
    assert row.is_provisioning_approved is True


def test_display_rows_defaults_active_true_provisioning_false_when_absent(tmp_path, monkeypatch):
    # _dev() fake devices carry neither attribute -- display_rows() must not crash,
    # and should default the same way nice4iot's own Device model does.
    paths = _paths(tmp_path)
    monkeypatch.setattr(rd, "_project_devices", _fake_devices(_dev("d")))

    row = rd.display_rows(paths, "proj")[0]
    assert row.is_active is True
    assert row.is_provisioning_approved is False


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
        "width": 800, "height": 480, "palette_id": "bw", "widgets": [],
    }))
    (paths.screen_dir / "mismatched.json").write_text(json.dumps({
        "width": 800, "height": 480, "palette_id": "bwr", "widgets": [],
    }))
    set_device_binding(paths, "d1", panel_type_id="waveshare_7in5_v2")  # 800x480 bw

    ids = rd.available_screen_ids(paths, "d1")
    assert "matching" in ids
    assert "mismatched" not in ids


def test_available_screen_ids_keeps_a_dangling_assignment_visible(tmp_path):
    paths = _paths(tmp_path)
    set_device_binding(paths, "d1", panel_type_id="waveshare_7in5_v2", screen_id="does-not-match")
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
