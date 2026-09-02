import pytest
from pydantic import ValidationError

from extensions.epaper.bookingsystem.backend import (
    booking_systems_adapter, booking_system_path, count_unreadable_booking_systems,
    create_booking_system, delete_booking_system, list_booking_systems, read_booking_system,
)
from extensions.epaper.bookingsystem.models import BookingSystemModel
from extensions.epaper.paths import EpaperPaths


def _paths(tmp_path) -> EpaperPaths:
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    return paths


# --- model -----------------------------------------------------------------

def test_booking_system_defaults_and_roundtrip():
    s = BookingSystemModel()
    assert s.id and s.name and s.type == "iCal"
    assert BookingSystemModel.model_validate_json(s.model_dump_json()) == s


def test_booking_system_ids_are_distinct():
    assert BookingSystemModel().id != BookingSystemModel().id


def test_booking_system_rejects_unknown_type():
    with pytest.raises(ValidationError):
        BookingSystemModel(type="exchange")  # not added yet


def test_booking_system_fields_carry_niceview_field_info():
    from niceview import FieldInfo
    for name in ("type", "url", "description"):
        md = BookingSystemModel.model_fields[name].metadata
        assert any(isinstance(m, FieldInfo) for m in md), f"{name} has no niceview FieldInfo"


def test_booking_system_header_defaults_to_a_user_agent_dict():
    s = BookingSystemModel()
    assert s.header == {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0"}


def test_booking_system_header_migrates_legacy_json_text():
    """Before 0.19, header was a JSON-text field (a textarea); stored files
    from before this change must still load instead of failing validation."""
    s = BookingSystemModel(header='{"X-Test": "1"}')
    assert s.header == {"X-Test": "1"}


def test_booking_system_header_migrates_legacy_empty_string():
    s = BookingSystemModel(header="")
    assert s.header == {}


def test_booking_system_header_accepts_a_plain_dict():
    s = BookingSystemModel(header={"X-Test": "1"})
    assert s.header == {"X-Test": "1"}


# --- storage ---------------------------------------------------------------

def test_create_names_file_after_id_and_reads_back(tmp_path):
    paths = _paths(tmp_path)
    s = create_booking_system(paths)
    assert booking_system_path(paths, s.id).exists()
    assert read_booking_system(paths, s.id) == s


def test_read_missing_is_none_without_writing(tmp_path):
    paths = _paths(tmp_path)
    assert read_booking_system(paths, "nope") is None
    assert list(paths.booking_dir.glob("*.json")) == []


def test_list_sorted_by_name(tmp_path):
    paths = _paths(tmp_path)
    adapter = booking_systems_adapter(paths)

    def _sys(name):
        s = create_booking_system(paths)
        s.name = name
        adapter.update(s)

    _sys("Beta")
    _sys("alpha")
    assert [s.name for s in list_booking_systems(paths)] == ["alpha", "Beta"]


def test_count_unreadable_booking_systems(tmp_path):
    """See test_room.py's test_count_unreadable_rooms() docstring: this diffs
    the real adapter's own count rather than re-reading each file, since a
    lenient single-file JsonAdapter.read() wouldn't actually catch a
    malformed file (BookingSystemModel is all-defaults too)."""
    paths = _paths(tmp_path)
    create_booking_system(paths)
    (paths.booking_dir / "broken.json").write_text("{")
    assert count_unreadable_booking_systems(paths) == 1


def test_delete_removes_file(tmp_path):
    paths = _paths(tmp_path)
    s = create_booking_system(paths)
    delete_booking_system(paths, s.id)
    assert read_booking_system(paths, s.id) is None
    delete_booking_system(paths, s.id)  # idempotent


def test_adapter_crud(tmp_path):
    paths = _paths(tmp_path)
    adapter = booking_systems_adapter(paths)

    s = adapter.create(BookingSystemModel())
    assert adapter.key_from_item(s) == s.id
    assert adapter.read(s.id).id == s.id
    assert [k for k, _ in adapter.items()] == [s.id]

    s.name = "iCal Uni"
    adapter.update(s)
    assert adapter.read(s.id).name == "iCal Uni"

    with pytest.raises(KeyError):
        adapter.read("nope")

    adapter.delete(s.id)
    assert list(adapter.items()) == []
