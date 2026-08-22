import datetime

from niceview.dataadapter import FileEntry

from extensions.epaper.ui.cards import _humanize_age
from extensions.epaper.ui.drilldown import _entry_caption


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


def test_default_widgets_have_no_empty_required_fields():
    """A newly added widget must validate as a whole: niceview enforces
    required fields at the widget level and commits an item only once it
    validates, so an empty required string (the old placeholder) would block
    every other edit in the widget's form until it is filled in."""
    from extensions.epaper.ui.widget_types import WIDGET_TYPES, new_widget
    for widget_type, entry in WIDGET_TYPES.items():
        widget = new_widget(widget_type)
        assert isinstance(widget, entry.model)
        empty = [name for name, field in entry.model.model_fields.items()
                 if field.is_required() and getattr(widget, name) in (None, '', [])]
        assert not empty, f"{widget_type} starts with empty required field(s): {empty}"


def test_every_widget_type_renders_its_form(tmp_path):
    """Each WIDGET_TYPES entry describes its form as a niceview layout, and a
    layout is only checked when it is rendered: a field name that doesn't
    exist on the model, or a select left without options, is a ValueError
    that takes the whole widget form down. Nothing else covers this, since
    the editor tests never open a widget."""
    from nicegui.client import Client
    from nicegui.page import page
    from niceview import ListAdapter

    from extensions.epaper.screen.models import WidgetModel
    from extensions.epaper.paths import EpaperPaths
    from extensions.epaper.ui.widget_types import WIDGET_TYPES, new_widget, render_widget_form

    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()  # no image files in it: the Image widget's file select had none to offer

    for widget_type in WIDGET_TYPES:
        widget = new_widget(widget_type)
        adapter = ListAdapter(WidgetModel, [widget])
        key = adapter.key_from_item(widget)
        with Client(page(f"/test-widget-form-{widget_type}"), request=None) as client:
            render_widget_form(widget, adapter, key, paths, lambda: None, lambda: None)
            headings = [e.text for e in client.elements.values()
                        if type(e).__name__ == "Label" and "text-subtitle2" in e.classes]
        assert headings == ["Layout", "Appearance", "Content"], \
            f"{widget_type} rendered sections {headings}"


def test_widget_forms_follow_the_field_they_switch_on(tmp_path):
    """Two widget types show different fields depending on one of their own
    values (WidgetType.refresh_on). Both directions have to render, and each
    must offer only the fields that apply -- a URL that is silently ignored
    because the source is a file is worse than no field at all."""
    from nicegui.client import Client
    from nicegui.page import page
    from niceview import ListAdapter

    from extensions.epaper.screen.models import WidgetModel
    from extensions.epaper.paths import EpaperPaths
    from extensions.epaper.ui.widget_types import new_widget, render_widget_form

    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()

    def labels_for(widget, name: str) -> set:
        adapter = ListAdapter(WidgetModel, [widget])
        with Client(page(f"/test-widget-switch-{name}"), request=None) as client:
            render_widget_form(widget, adapter, adapter.key_from_item(widget),
                               paths, lambda: None, lambda: None)
            return {e._props.get("label") for e in client.elements.values()}

    image = new_widget("Image")
    image.source_type = "url"
    assert "Url" in labels_for(image, "url") and "File" not in labels_for(image, "url2")
    image.source_type = "file"
    assert "File" in labels_for(image, "file") and "Url" not in labels_for(image, "file2")

    entity = new_widget("HomeAssistant")
    entity.display = "value"
    assert "Alignment" in labels_for(entity, "value")
    entity.display = "gauge"
    gauge_labels = labels_for(entity, "gauge")
    assert "Min value" in gauge_labels and "Alignment" not in gauge_labels


def test_new_schedule_rule_has_a_starter_time():
    """Same reason as above: `times` is required, so a new weekly rule can't
    start out empty or its weekday/month fields wouldn't commit."""
    from extensions.epaper.schedule.ui import _default_rule
    rule = _default_rule()
    assert rule.times
    assert rule.by_weekdays and rule.by_months  # "every", not an empty restriction


def test_global_config_card_renders_every_field():
    """Regression: the form excluded 'epaper_color_models' after that field
    had been removed from GlobalConfig, which ModelForm rejects with a
    ValueError -- so the whole global settings card came up empty, in
    nice4iot and standalone alike. Renders the card for real, since the
    failure was in building it, not in any helper below it."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.global_config.models import GlobalConfig
    from extensions.epaper.global_config.ui import global_config_fields

    with Client(page("/test-global-config"), request=None) as client:
        global_config_fields(persist=lambda: None)
        labels = {e._props.get("label") for e in client.elements.values()}

    # a field from each section, so a silently dropped group is noticed too
    for expected in ("Locale", "Font name", "Color accent", "Latitude",
                     "Weather error", "Home Assistant URL"):
        assert expected in labels, f"{expected!r} missing from the global settings card"

    # every setting should have a widget; none may be skipped silently
    assert len([e for e in labels if e]) >= len(GlobalConfig.model_fields)


def _element_type_names(client) -> list:
    return [type(e).__name__ for e in client.elements.values()]


def test_simplified_ui_nav_leaves_are_the_content_sections():
    """The sidebar's leaves (the addressable views) are exactly the four
    content sections, Templates right after Rooms; Settings is a group and
    never a view itself."""
    from extensions.epaper.ui.simplified_ui import _nav
    from extensions.epaper.ui.simplified_ui.layout import _flatten

    nav = _nav()
    assert list(_flatten(nav)) == ["rooms", "templates", "displays", "booking"]
    settings = next(i for i in nav if i.id == "settings")
    assert settings.render is None and [c.id for c in settings.children] == ["booking"]


def _simplified_paths(tmp_path):
    from extensions.epaper.paths import EpaperPaths
    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    return paths


def test_simplified_ui_frame_renders_header_and_drawer(tmp_path):
    """The whole page frame builds: a header, a left drawer (the sidebar)
    and the landing (Rooms) content. Renders for real -- the failure mode
    this guards is build_page() raising while assembling the layout."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.ui.simplified_ui import render

    with Client(page("/test-simplified-frame"), request=None) as client:
        render("demo-project", paths=_simplified_paths(tmp_path))
        names = _element_type_names(client)
        labels = {e.text for e in client.elements.values()
                  if type(e).__name__ in ("Label", "ItemLabel")}

    assert "Header" in names and "LeftDrawer" in names
    assert "E-Paper Rooms" in labels  # brand
    # landing view is the rooms list (DrillDownWrapper), titled "Rooms"
    assert "Rooms" in labels


def test_simplified_ui_room_detail_lays_out_every_setting(tmp_path):
    """The room detail lays out the full (English) field set -- number, name,
    building, floor, type, capacity, photo, notes, booking system, iCal URL --
    with labels/widgets taken from RoomModel's own FieldInfo, plus the three
    tabs. Renders the detail body directly (the list wrapper starts on the list)."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.room.backend import rooms_adapter, create_room
    from extensions.epaper.ui.simplified_ui import _nav
    from extensions.epaper.ui.simplified_ui.layout import Shell, _flatten
    from extensions.epaper.room.simplified_ui import _render_detail

    paths = _simplified_paths(tmp_path)
    room = create_room(paths)
    shell = Shell("demo-project", paths, _flatten(_nav()))
    with Client(page("/test-simplified-room"), request=None) as client:
        _render_detail(shell, rooms_adapter(paths), room.id)
        labels = {e._props.get("label") for e in client.elements.values()}
        tab_labels = {e._props.get("label") for e in client.elements.values()
                      if type(e).__name__ == "Tab"}

    for field in ("Room number", "Room name", "Building", "Floor", "Room type",
                  "Capacity", "Photo", "Description", "Booking system", "iCal URL"):
        assert field in labels, f"{field!r} missing from room settings"
    assert {"Occupancy", "Settings", "Displays"} <= tab_labels


def test_room_displays_panel_shows_summary_and_bound_devices(tmp_path, monkeypatch):
    """The Displays tab leads with a room summary (room_label + type, then
    building/floor) and lists every device bound to the room, titled by
    device name with the screen as subtitle."""
    import datetime
    import types

    import extensions.epaper.display.backend as display_backend
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.devicebinding.backend import set_device_binding
    from extensions.epaper.room.backend import create_room
    from extensions.epaper.room.simplified_ui import _displays_panel
    from extensions.epaper.ui.simplified_ui import _nav
    from extensions.epaper.ui.simplified_ui.layout import Shell, _flatten

    paths = _simplified_paths(tmp_path)
    room = create_room(paths)
    room.room_number, room.room_name = "A-101", "North Conference"
    room.building, room.floor = "Main", "2"
    from extensions.epaper.room.backend import room_adapter
    room_adapter(paths, room.id).save(room)
    set_device_binding(paths, "sign-1", room_id=room.id, screen_id="weather")

    monkeypatch.setattr(display_backend, "_project_devices", lambda project: [
        types.SimpleNamespace(name="sign-1", last_seen_at=datetime.datetime.now(datetime.timezone.utc)),
    ])

    shell = Shell("demo-project", paths, _flatten(_nav()))
    with Client(page("/test-room-displays"), request=None) as client:
        _displays_panel(shell, room.id)
        labels = {e.text for e in client.elements.values()
                  if type(e).__name__ in ("Label", "ItemLabel")}

    assert "A-101 (North Conference) · Meeting room" in labels
    assert "Main, 2" in labels
    assert "sign-1" in labels  # list row title (device_name)
    assert "weather" in labels  # list row subtitle (screen_id)


def test_rooms_project_tab_grid_resolves_booking_system_name(tmp_path):
    """The unsimplified Rooms project tab (room/ui.py) is an EditGridWrapper over
    the rooms directory. Its Booking system column is a modelselect resolved
    through the booking-systems repository, so it shows the system's name
    (BookingSystemModel.__str__), not the raw id. Guards the whole wiring:
    the modelselect field on RoomModel, the wrapper's with_repositories, and
    __str__."""
    import json

    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.bookingsystem.backend import booking_systems_adapter, create_booking_system
    from extensions.epaper.room.backend import create_room, rooms_adapter
    from extensions.epaper.room.ui import rooms_wrapper

    paths = _simplified_paths(tmp_path)
    system = create_booking_system(paths)
    system.name = "iCal Uni"
    booking_systems_adapter(paths).update(system)
    room = create_room(paths)
    room.booking_system_id = system.id
    rooms_adapter(paths).update(room)

    with Client(page("/test-rooms-grid"), request=None) as client:
        rooms_wrapper(paths, "demo-project").render()
        grids = [e for e in client.elements.values()
                 if isinstance(getattr(e, "options", None), dict) and "columnDefs" in e.options]
        assert grids, "rooms project tab did not render an ag-grid"
        blob = json.dumps(grids[0].options, default=str)

    assert "iCal Uni" in blob, \
        "booking system name not resolved in the grid (modelselect/repository/__str__ wiring)"


def test_simplified_ui_booking_form_lays_out_fields():
    """The BookingSystemModel form (rendered by the booking DrillDownWrapper's
    default detail) exposes the system's fields."""
    from nicegui.client import Client
    from nicegui.page import page
    from niceview import ModelForm

    from extensions.epaper.bookingsystem.models import BookingSystemModel

    with Client(page("/test-simplified-booking"), request=None) as client:
        ModelForm.from_item(BookingSystemModel()).render()
        labels = {e._props.get("label") for e in client.elements.values()}

    for field in ("Name", "Type", "Url", "Description"):
        assert field in labels, f"{field!r} missing from booking system form"


def test_room_booking_select_lists_configured_systems(tmp_path):
    """A room's booking_system_id is a select of the configured systems: its
    options come from storage, not the model, and include each system by name."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.bookingsystem.backend import booking_systems_adapter, create_booking_system
    from extensions.epaper.room.backend import rooms_adapter, create_room
    from extensions.epaper.ui.simplified_ui import _nav
    from extensions.epaper.ui.simplified_ui.layout import Shell, _flatten
    from extensions.epaper.room.simplified_ui import _render_detail

    paths = _simplified_paths(tmp_path)
    system = create_booking_system(paths)
    system.name = "iCal Uni"
    booking_systems_adapter(paths).update(system)
    room = create_room(paths)
    shell = Shell("demo-project", paths, _flatten(_nav()))
    with Client(page("/test-room-booking-select"), request=None) as client:
        _render_detail(shell, rooms_adapter(paths), room.id)
        selects = [e for e in client.elements.values()
                   if e._props.get("label") == "Booking system"]

    assert selects, "no 'Booking system' select rendered"
    option_labels = {o.get("label") for o in selects[0]._props.get("options", [])}
    assert "iCal Uni" in option_labels


def test_standalone_global_tab_links_to_the_simplified_ui():
    """The Global tab shows the 'Open simplified UI' card (above the settings
    card) that navigates to the standalone simplified-UI route."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.ui.standalone import SIMPLIFIED_ROUTE, _simplified_ui_link

    with Client(page("/test-simplified-link"), request=None) as client:
        _simplified_ui_link()
        texts = {e.text for e in client.elements.values()
                 if type(e).__name__ in ("Label", "Button")}

    assert "Simplified UI" in texts and "Open" in texts
    assert SIMPLIFIED_ROUTE == "/simplified"
