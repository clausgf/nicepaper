import datetime

from extensions.epaper.util import check_filename, humanize_age


def test_humanize_age():
    now = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
    d = datetime.timedelta
    assert humanize_age(None, now) == "never"
    assert humanize_age(now - d(seconds=30), now) == "just now"
    assert humanize_age(now - d(minutes=5), now) == "5 min ago"
    assert humanize_age(now - d(hours=3), now) == "3 h ago"
    assert humanize_age(now - d(days=2), now) == "2 d ago"


def test_check_filename_accepts_simple_names():
    assert check_filename("screen1.json")
    assert check_filename("my-screen_2+x.png")


def test_check_filename_rejects_path_traversal():
    assert not check_filename("../etc.json")
    assert not check_filename("a/b.json")
    assert not check_filename("..")
    assert not check_filename("")


def test_check_filename_requires_extension():
    assert not check_filename("noextension")
    assert not check_filename("trailingdot.")
