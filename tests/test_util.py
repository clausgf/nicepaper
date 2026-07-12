from extensions.epaper.util import check_filename


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
