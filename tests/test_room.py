import asyncio
import datetime

import pytest

from extensions.epaper.core.datasources.ical import IcalStatus
from extensions.epaper.room.backend import (
    count_unreadable_rooms, create_room, delete_room, get_room_events, list_rooms, read_room,
    room_adapter, room_path,
)
from extensions.epaper.room.photo import delete_room_photo, room_photo_path, save_room_photo
from extensions.epaper.paths import EpaperPaths
import extensions.epaper.room.backend as room_backend


def _status(events: list, id: str = "room-x") -> IcalStatus:
    return IcalStatus(id=id, events=events, last_update=None, fresh=False,
                      failing=False, fail_count=0, retry_after=None, error=None)


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


def test_count_unreadable_rooms(tmp_path):
    """count_unreadable_rooms() diffs the real Rooms-list adapter (files on
    disk vs. what rooms_adapter() actually lists) rather than re-reading
    each file itself -- a single-file JsonAdapter.read() (as list_rooms()
    above does) is lenient by default and recovers a malformed file into a
    *default* RoomModel instead of raising, so it would never catch this."""
    paths = _paths(tmp_path)
    create_room(paths)  # a real, valid room
    (paths.room_dir / "broken.json").write_text("not json at all")
    assert count_unreadable_rooms(paths) == 1


def test_count_unreadable_rooms_is_zero_when_all_valid(tmp_path):
    paths = _paths(tmp_path)
    create_room(paths)
    create_room(paths)
    assert count_unreadable_rooms(paths) == 0


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


def _room_with_booking_system(paths, **system_fields):
    from extensions.epaper.bookingsystem.backend import booking_system_adapter, create_booking_system

    system = create_booking_system(paths)
    for name, value in system_fields.items():
        setattr(system, name, value)
    booking_system_adapter(paths, system.id).save(system)

    room = create_room(paths)
    room.booking_system_id = system.id
    room_adapter(paths, room.id).save(room)
    return room, system


def test_get_room_events_without_booking_system_raises(tmp_path):
    paths = _paths(tmp_path)
    room = create_room(paths)
    with pytest.raises(ValueError, match="no booking system"):
        asyncio.run(get_room_events(paths, room))


def test_get_room_events_with_dangling_booking_system_raises(tmp_path):
    paths = _paths(tmp_path)
    room = create_room(paths)
    room.booking_system_id = "does-not-exist"
    room_adapter(paths, room.id).save(room)
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(get_room_events(paths, room))


def test_get_room_events_without_url_raises(tmp_path):
    paths = _paths(tmp_path)
    room, _system = _room_with_booking_system(paths)  # url="" by default
    with pytest.raises(ValueError, match="no URL"):
        asyncio.run(get_room_events(paths, room))


def test_get_room_events_prefers_room_url_over_system_url(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room, system = _room_with_booking_system(
        paths, url="https://example.com/system.ics", header={"X-Test": "1"})
    room.booking_ical_url = "https://example.com/room-specific.ics"
    room_adapter(paths, room.id).save(room)

    captured: dict = {}

    async def fake_get_from_ical(ical_dir, organizer_names_file, id, url, **kwargs):
        captured.update(url=url, **kwargs)
        return _status(["EVENT"])

    monkeypatch.setattr(room_backend, "get_from_ical", fake_get_from_ical)
    events = asyncio.run(get_room_events(paths, room))

    assert events == ["EVENT"]
    assert captured["url"] == "https://example.com/room-specific.ics"
    assert captured["headers"] == {"X-Test": "1"}
    assert captured["username"] == system.username


def test_get_room_events_falls_back_to_system_url(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room, _system = _room_with_booking_system(paths, url="https://example.com/system.ics")

    captured: dict = {}

    async def fake_get_from_ical(ical_dir, organizer_names_file, id, url, **kwargs):
        captured["url"] = url
        return _status([])

    monkeypatch.setattr(room_backend, "get_from_ical", fake_get_from_ical)
    asyncio.run(get_room_events(paths, room))
    assert captured["url"] == "https://example.com/system.ics"


def test_get_room_events_passes_system_timing_as_seconds_and_days(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room, _system = _room_with_booking_system(
        paths, url="https://example.com/system.ics",
        update_interval=datetime.timedelta(minutes=5),
        max_days_ahead=datetime.timedelta(days=14))

    captured: dict = {}

    async def fake_get_from_ical(ical_dir, organizer_names_file, id, url, **kwargs):
        captured.update(kwargs)
        return _status([])

    monkeypatch.setattr(room_backend, "get_from_ical", fake_get_from_ical)
    asyncio.run(get_room_events(paths, room))
    assert captured["update_interval_s"] == 300
    assert captured["max_days"] == 14


def test_room_photo_round_trip(tmp_path):
    paths = _paths(tmp_path)
    room = create_room(paths)
    assert room_photo_path(paths, room.id) is None

    save_room_photo(paths, room.id, "hallway.jpg", b"fake-jpeg-bytes")
    path = room_photo_path(paths, room.id)
    assert path is not None
    assert path.name == f"{room.id}.jpg"
    assert path.read_bytes() == b"fake-jpeg-bytes"


def test_room_photo_replace_removes_old_extension(tmp_path):
    paths = _paths(tmp_path)
    room = create_room(paths)
    save_room_photo(paths, room.id, "first.jpg", b"one")
    save_room_photo(paths, room.id, "second.png", b"two")

    assert [p.name for p in paths.room_photo_dir.glob(f"{room.id}.*")] == [f"{room.id}.png"]
    assert room_photo_path(paths, room.id).read_bytes() == b"two"


def test_room_photo_rejects_unsupported_extension(tmp_path):
    paths = _paths(tmp_path)
    room = create_room(paths)
    with pytest.raises(ValueError, match="Unsupported image type"):
        save_room_photo(paths, room.id, "not-an-image.txt", b"text")
    assert room_photo_path(paths, room.id) is None


def test_delete_room_photo_is_idempotent(tmp_path):
    paths = _paths(tmp_path)
    room = create_room(paths)
    delete_room_photo(paths, room.id)  # no photo yet -- must not raise

    save_room_photo(paths, room.id, "photo.png", b"data")
    delete_room_photo(paths, room.id)
    assert room_photo_path(paths, room.id) is None
    delete_room_photo(paths, room.id)  # already gone -- still fine


def test_get_room_events_passes_none_for_empty_headers(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    room, _system = _room_with_booking_system(
        paths, url="https://example.com/system.ics", header={})

    captured: dict = {}

    async def fake_get_from_ical(ical_dir, organizer_names_file, id, url, **kwargs):
        captured.update(kwargs)
        return _status([])

    monkeypatch.setattr(room_backend, "get_from_ical", fake_get_from_ical)
    asyncio.run(get_room_events(paths, room))
    assert captured["headers"] is None
