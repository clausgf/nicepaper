from extensions.epaper.ui.panels import _rename_file


def test_rename_file_success(tmp_path):
    old = tmp_path / "old.json"
    old.write_text("{}")

    success, message = _rename_file(tmp_path, old, "new")

    assert success
    assert "new.json" in message
    assert not old.exists()
    assert (tmp_path / "new.json").exists()
    assert (tmp_path / "new.json").read_text() == "{}"


def test_rename_file_adds_json_suffix_if_missing(tmp_path):
    old = tmp_path / "old.json"
    old.write_text("{}")

    success, _message = _rename_file(tmp_path, old, "new")

    assert success
    assert (tmp_path / "new.json").exists()


def test_rename_file_rejects_invalid_name(tmp_path):
    old = tmp_path / "old.json"
    old.write_text("{}")

    success, message = _rename_file(tmp_path, old, "../escape")

    assert not success
    assert "Invalid" in message
    assert old.exists()


def test_rename_file_rejects_existing_target(tmp_path):
    old = tmp_path / "old.json"
    old.write_text("{}")
    (tmp_path / "taken.json").write_text("{}")

    success, message = _rename_file(tmp_path, old, "taken")

    assert not success
    assert "already exists" in message
    assert old.exists()
