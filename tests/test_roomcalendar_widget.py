import asyncio
import datetime

from PIL import Image

from extensions.epaper.bookingsystem.backend import booking_system_adapter, create_booking_system
from extensions.epaper.catalog.models import Palette
from extensions.epaper.core.datasources.ical import IcalStatus
from extensions.epaper.core.drawingcontext import DrawingContext
from extensions.epaper.core.widgets.roomcalendar import RoomCalendarWidget
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.room.backend import create_room, room_adapter
from extensions.epaper.screen.models import RoomCalendarWidgetModel
import extensions.epaper.room.backend as room_backend

_BWR = Palette(id="bwr", name="test", palette=[(0, 0, 0), (255, 255, 255), (255, 0, 0)])


def _paths(tmp_path) -> EpaperPaths:
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    return paths


def _room_with_booking_system(paths, **system_fields):
    system = create_booking_system(paths)
    system.url = "https://example.com/calendar.ics"
    for name, value in system_fields.items():
        setattr(system, name, value)
    booking_system_adapter(paths, system.id).save(system)

    room = create_room(paths)
    room.room_number = "101"
    room.room_name = "Conference Room"
    room.booking_system_id = system.id
    room_adapter(paths, room.id).save(room)
    return room, system


def _event(categories: str = "") -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    return {
        "dtstart": now.isoformat(),
        "dtend": (now + datetime.timedelta(hours=1)).isoformat(),
        "organizer": "Alice",
        "summary": "Team sync",
        "categories": categories,
    }


def _render(paths, room, palette=None) -> Image.Image:
    config = RoomCalendarWidgetModel(position_x=0, position_y=0, size_width=800, size_height=480)
    widget = RoomCalendarWidget("0", config)
    image = Image.new("RGB", (800, 480), color=(255, 255, 255))
    ctx = DrawingContext(image, "#ffffff", "#000000", ("Ubuntu-Regular.ttf", 14),
                         paths=paths, room=room, palette=palette)
    asyncio.run(widget.draw(ctx))
    return image


def _has_pixel(image: Image.Image, color: tuple) -> bool:
    w, h = image.size
    return any(image.getpixel((x, y)) == color for x in range(w) for y in range(h))


def _status(events: list) -> IcalStatus:
    return IcalStatus(id="room-x", events=events, last_update=None, fresh=False,
                      failing=False, fail_count=0, retry_after=None, error=None)


def test_no_room_renders_placeholder_without_crashing(tmp_path):
    paths = _paths(tmp_path)
    image = _render(paths, room=None)
    assert image.size == (800, 480)
    assert _has_pixel(image, (0, 0, 0)), "placeholder text should have drawn something"


def test_room_without_booking_system_shows_error_without_crashing(tmp_path):
    paths = _paths(tmp_path)
    room = create_room(paths)
    image = _render(paths, room=room)
    assert image.size == (800, 480)


def test_category_color_reaches_the_drawn_card(tmp_path, monkeypatch):
    room, system = _room_with_booking_system(paths := _paths(tmp_path))
    system.category_colors = {"meeting": "#ff0000"}
    booking_system_adapter(paths, system.id).save(system)

    async def fake_get_from_ical(ical_dir, organizer_names_file, id, url, **kwargs):
        return _status([_event(categories="meeting")])

    monkeypatch.setattr(room_backend, "get_from_ical", fake_get_from_ical)

    image = _render(paths, room=room, palette=_BWR)
    assert _has_pixel(image, (255, 0, 0)), "the mapped category color should reach the card outline"


def test_unmapped_category_falls_back_to_primary_color(tmp_path, monkeypatch):
    room, system = _room_with_booking_system(paths := _paths(tmp_path))
    system.category_colors = {"meeting": "#ff0000"}
    booking_system_adapter(paths, system.id).save(system)

    async def fake_get_from_ical(ical_dir, organizer_names_file, id, url, **kwargs):
        return _status([_event(categories="other")])

    monkeypatch.setattr(room_backend, "get_from_ical", fake_get_from_ical)

    image = _render(paths, room=room, palette=_BWR)
    assert not _has_pixel(image, (255, 0, 0)), "an unmapped category must not pick up an unrelated color"


def test_off_palette_color_falls_back_to_black_not_a_nearest_guess(tmp_path, monkeypatch):
    """A booking system isn't tied to one panel (several rooms with
    different panels can share it), so there's no single "closest" palette
    member that would be right for all of them -- a color the active panel
    can't show exactly falls back to plain black instead (see
    core/widgets/roomcalendar.py::_event_category_color). "#0000ff" (blue)
    isn't a member of _BWR (black/white/red); a nearest-Euclidean-distance
    guess would have picked red here, which this guards against."""
    room, system = _room_with_booking_system(paths := _paths(tmp_path))
    system.category_colors = {"meeting": "#0000ff"}
    booking_system_adapter(paths, system.id).save(system)

    async def fake_get_from_ical(ical_dir, organizer_names_file, id, url, **kwargs):
        return _status([_event(categories="meeting")])

    monkeypatch.setattr(room_backend, "get_from_ical", fake_get_from_ical)

    image = _render(paths, room=room, palette=_BWR)
    assert _has_pixel(image, (0, 0, 0))
    assert not _has_pixel(image, (255, 0, 0))
    assert not _has_pixel(image, (0, 0, 255))
