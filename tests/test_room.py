from extensions.epaper.room.backend import (
    create_room, delete_room, list_rooms, read_room, room_path,
)
from extensions.epaper.paths import EpaperPaths


def _paths(tmp_path) -> EpaperPaths:
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    return paths


def test_create_room_names_the_file_after_its_id(tmp_path):
    paths = _paths(tmp_path)
    room = create_room(paths)
    # the file is named by the stable surrogate id, so bindings referencing
    # the id find it regardless of later renames
    assert room_path(paths, room.id).exists()
    assert read_room(paths, room.id) == room


def test_create_room_generates_distinct_ids(tmp_path):
    paths = _paths(tmp_path)
    a, b = create_room(paths), create_room(paths)
    assert a.id != b.id
    assert len(list(paths.room_dir.glob("*.json"))) == 2


def test_read_missing_room_is_none_and_writes_nothing(tmp_path):
    paths = _paths(tmp_path)
    assert read_room(paths, "does-not-exist") is None
    # must not have created a junk file (JsonAdapter create_if_not_exist=False)
    assert list(paths.room_dir.glob("*.json")) == []


def test_rename_keeps_id_and_file(tmp_path):
    paths = _paths(tmp_path)
    room = create_room(paths)
    # "renaming" edits the name and saves through the same id/file
    room.room_name = "Konferenz Nord"
    room.room_number = "A-101"
    from extensions.epaper.room.backend import room_adapter
    room_adapter(paths, room.id).save(room)

    reloaded = read_room(paths, room.id)
    assert reloaded.id == room.id  # id never changes
    assert (reloaded.room_name, reloaded.room_number) == ("Konferenz Nord", "A-101")
    assert [p.stem for p in paths.room_dir.glob("*.json")] == [room.id]


def test_list_rooms_sorted_by_name_then_number(tmp_path):
    paths = _paths(tmp_path)
    from extensions.epaper.room.backend import room_adapter

    def _room(name, number):
        r = create_room(paths)
        r.room_name, r.room_number = name, number
        room_adapter(paths, r.id).save(r)

    _room("Beta", "2")
    _room("alpha", "9")
    _room("Beta", "1")
    ordered = [(r.room_name, r.room_number) for r in list_rooms(paths)]
    assert ordered == [("alpha", "9"), ("Beta", "1"), ("Beta", "2")]


def test_delete_room_removes_the_file(tmp_path):
    paths = _paths(tmp_path)
    room = create_room(paths)
    delete_room(paths, room.id)
    assert read_room(paths, room.id) is None
    delete_room(paths, room.id)  # idempotent, missing_ok


def test_rooms_adapter_crud(tmp_path):
    from extensions.epaper.room.backend import rooms_adapter
    from extensions.epaper.room.models import RoomModel
    paths = _paths(tmp_path)
    adapter = rooms_adapter(paths)

    # DrillDownWrapper's default Add: create(RoomModel()) -> fresh id + file
    room = adapter.create(RoomModel())
    assert adapter.key_from_item(room) == room.id
    assert adapter.read(room.id).id == room.id
    assert [k for k, _ in adapter.items()] == [room.id]

    # update persists through the same id/file
    room.room_name = "Lab 1"
    adapter.update(room)
    assert adapter.read(room.id).room_name == "Lab 1"

    # missing key raises (DrillDownWrapper shows its not-found state)
    import pytest
    with pytest.raises(KeyError):
        adapter.read("nope")

    adapter.delete(room.id)
    assert list(adapter.items()) == []
