import datetime

from niceview.dataadapter import FileEntry

from extensions.epaper.ui.panels import _entry_caption, _humanize_age


def _entry(size: int) -> FileEntry:
    return FileEntry(name="x", mtime=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc), size=size)


def test_entry_caption_uses_bytes_below_1024():
    assert "1023 B" in _entry_caption(_entry(1023))


def test_entry_caption_uses_kib_below_1_mib():
    assert "1.0 kiB" in _entry_caption(_entry(1024))


def test_entry_caption_uses_mib_at_1_mib_and_above():
    assert "1.0 MiB" in _entry_caption(_entry(1024**2))


def test_humanize_age():
    now = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
    d = datetime.timedelta
    assert _humanize_age(None, now) == "never"
    assert _humanize_age(now - d(seconds=30), now) == "just now"
    assert _humanize_age(now - d(minutes=5), now) == "5 min ago"
    assert _humanize_age(now - d(hours=3), now) == "3 h ago"
    assert _humanize_age(now - d(days=2), now) == "2 d ago"
