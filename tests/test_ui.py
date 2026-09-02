import datetime

from niceview.dataadapter import FileEntry

from extensions.epaper.ui.drilldown import _entry_caption


def _entry(size: int) -> FileEntry:
    return FileEntry(name="x", mtime=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc), size=size)


def test_entry_caption_uses_bytes_below_1024():
    assert "1023 B" in _entry_caption(_entry(1023))


def test_entry_caption_uses_kib_below_1_mib():
    assert "1.0 kiB" in _entry_caption(_entry(1024))


def test_entry_caption_uses_mib_at_1_mib_and_above():
    assert "1.0 MiB" in _entry_caption(_entry(1024**2))


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


def _new_widget_form(tmp_path, widget_type, *, palette=None):
    """render_widget_form() for a fresh widget of widget_type, returning the
    client's elements for inspection. Shared by the compact-appearance-field
    tests below."""
    from nicegui.client import Client
    from nicegui.page import page
    from niceview import ListAdapter

    from extensions.epaper.paths import EpaperPaths
    from extensions.epaper.screen.models import WidgetModel
    from extensions.epaper.ui.widget_types import new_widget, render_widget_form

    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()

    widget = new_widget(widget_type)
    adapter = ListAdapter(WidgetModel, [widget])
    key = adapter.key_from_item(widget)
    with Client(page(f"/test-widget-appearance-{widget_type}"), request=None) as client:
        render_widget_form(widget, adapter, key, paths, lambda: None, lambda: None,
                           palette=palette)
        elements = list(client.elements.values())
    return elements


def test_widget_appearance_extras_restrict_colors_to_the_palette(tmp_path):
    """The compact color fields (ui/compact_fields.py) must only offer the
    current screen's palette colors -- one swatch button per palette entry,
    styled with that entry's own hex -- plus the font icon button; both are
    absent for widget types with colors=False/font=False (Image)."""
    from extensions.epaper.catalog.models import Palette

    palette = Palette(id="test", name="Test", palette=[(0, 0, 0), (255, 255, 255), (255, 0, 0)])
    elements = _new_widget_form(tmp_path, "Text", palette=palette)

    swatch_colors = {e._style.get("background-color") for e in elements
                     if type(e).__name__ == "Button" and "background-color" in e._style}
    palette_hex = {f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette.palette}
    assert palette_hex <= swatch_colors, \
        f"expected every palette color among the swatches, got {swatch_colors}"

    font_icons = [e for e in elements if type(e).__name__ == "Button" and e.icon == "text_fields"]
    assert len(font_icons) == 1, "expected exactly one compact font field"

    assert not any(type(e).__name__ == "ColorInput" for e in elements), \
        "a palette was given, so the unrestricted color_input fallback shouldn't render"


def test_widget_appearance_extras_fall_back_without_a_palette(tmp_path):
    """No palette resolvable for the screen (e.g. palette_id unset) -> the
    color fields fall back to a plain, unrestricted ui.color_input."""
    elements = _new_widget_form(tmp_path, "Text", palette=None)
    color_inputs = [e for e in elements if type(e).__name__ == "ColorInput"]
    assert len(color_inputs) == 2, "expected one color_input per color field (primary, background)"


def test_image_widget_has_no_appearance_extras(tmp_path):
    """Image opts out of both font and colors (font=False, colors=False) --
    no compact font icon, no color swatches/inputs at all."""
    from extensions.epaper.catalog.models import Palette

    palette = Palette(id="test", name="Test", palette=[(0, 0, 0), (255, 255, 255)])
    elements = _new_widget_form(tmp_path, "Image", palette=palette)
    assert not any(type(e).__name__ == "ColorInput" for e in elements)
    assert not any(type(e).__name__ == "Button" and e.icon == "text_fields" for e in elements)


def test_weather_chart_line_style_defaults_to_solid_and_renders_as_select(tmp_path):
    from extensions.epaper.screen.models import WeatherChartWidgetModel

    assert WeatherChartWidgetModel(position_x=0, position_y=0).line_style_primary == "solid"

    elements = _new_widget_form(tmp_path, "WeatherChart")
    selects = {e._props.get("label"): e for e in elements
              if type(e).__name__ == "Select" and e._props.get("label") in ("Line style primary", "Line style secondary")}
    assert selects.keys() == {"Line style primary", "Line style secondary"}, \
        "secondary_metric needs its own line style select, independent of primary_metric's"
    for select in selects.values():
        assert set(select.options) == {"solid", "dashed", "dotted"}


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
    assert "Min value" not in labels_for(entity, "value")
    entity.display = "bar"
    assert "Min value" in labels_for(entity, "bar")


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
    for expected in ("Locale", "Font name", "iCal retry min s",
                     "Weather error", "Update interval s"):
        assert expected in labels, f"{expected!r} missing from the global settings card"

    # every setting should have a widget; none may be skipped silently
    assert len([e for e in labels if e]) >= len(GlobalConfig.model_fields)


def test_project_config_card_renders_every_field(tmp_path):
    """Same regression guard as test_global_config_card_renders_every_field,
    for ProjectConfig's own form (project_config/ui.py)."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.paths import EpaperPaths
    from extensions.epaper.project_config.models import ProjectConfig
    from extensions.epaper.project_config.ui import project_config_fields

    paths = EpaperPaths(root=tmp_path)
    with Client(page("/test-project-config"), request=None) as client:
        project_config_fields(paths)
        labels = {e._props.get("label") for e in client.elements.values()}

    for expected in ("Latitude", "Longitude", "Home Assistant URL", "Long-lived access token"):
        assert expected in labels, f"{expected!r} missing from the project settings card"
    assert len([e for e in labels if e]) >= len(ProjectConfig.model_fields)


def _element_type_names(client) -> list:
    return [type(e).__name__ for e in client.elements.values()]


def test_simplified_ui_nav_leaves_are_the_content_sections():
    """The sidebar's leaves (the addressable views) are exactly the eight
    content sections, Templates right after Rooms; Settings is a group and
    never a view itself, with Schedule, Booking systems, Organizer names,
    Project settings and Global settings in that order."""
    from extensions.epaper.ui.simplified_ui import _nav
    from extensions.epaper.ui.simplified_ui.layout import _flatten

    nav = _nav()
    assert list(_flatten(nav)) == [
        "rooms", "templates", "displays", "schedule", "booking", "organizer", "project", "global",
    ]
    settings = next(i for i in nav if i.id == "settings")
    assert settings.render is None and [c.id for c in settings.children] == [
        "schedule", "booking", "organizer", "project", "global",
    ]


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
        render("demo-project", paths=_simplified_paths(tmp_path), root_path="/test-simplified-frame")
        names = _element_type_names(client)
        labels = {e.text for e in client.elements.values()
                  if type(e).__name__ in ("Label", "ItemLabel")}

    assert "Header" in names and "LeftDrawer" in names
    assert "E-Paper Rooms" in labels  # brand
    # landing view is the rooms list (DrillDownWrapper), titled "Rooms"
    assert "Rooms" in labels


def test_templates_section_lists_real_and_synthetic_screens(tmp_path):
    """Templates lists every screen file (shared storage with the
    non-simplified editor) plus the auto-generated Room Calendar templates
    (one per distinct panel-catalog resolution/palette), each as a card with
    its panel_label/generated name."""
    import json

    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.screen.simplified_ui import render_templates
    from extensions.epaper.ui.simplified_ui.layout import Shell

    paths = _simplified_paths(tmp_path)
    (paths.screen_dir / "my-screen.json").write_text(json.dumps({
        "width": 200, "height": 100,
        "widgets": [{"widget_type": "Text", "position_x": 0, "position_y": 0, "text": "hi"}],
    }))

    shell = Shell("demo-project", paths, image_base_url="/api/screen")
    with Client(page("/test-templates"), request=None) as client:
        render_templates(shell)
        labels = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}

    assert any("200x100" in label for label in labels), "the real screen's panel label should be listed"
    assert any(label.startswith("Room Calendar ") for label in labels), \
        "the auto-generated templates should be listed too"


def test_render_templates_flags_a_screen_file_that_failed_to_parse(tmp_path):
    """A screen file that can't parse (ScreenModel.width/height are required,
    no default -- unlike RoomModel/BookingSystemModel, which are all
    defaults) is skipped by _real_screens() rather than shown as a ghost
    default screen, and unreadable_items_banner() surfaces the count."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.screen.simplified_ui import render_templates
    from extensions.epaper.ui.simplified_ui.layout import Shell

    paths = _simplified_paths(tmp_path)
    (paths.screen_dir / "broken.json").write_text("not json at all")

    shell = Shell("demo-project", paths, image_base_url="/api/screen")
    with Client(page("/test-templates-broken"), request=None) as client:
        render_templates(shell)
        labels = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}

    assert any("1 screen(s) failed to load" in label for label in labels)


def test_simplified_ui_room_detail_lays_out_every_setting(tmp_path):
    """The room detail lays out the full (English) field set -- number, name,
    building, floor, type, capacity, notes, description, booking system,
    iCal URL -- with labels/widgets taken from RoomModel's own FieldInfo,
    plus the three tabs. Renders the detail body directly (the list wrapper
    starts on the list)."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.room.backend import rooms_adapter, create_room
    from extensions.epaper.ui.simplified_ui.layout import Shell
    from extensions.epaper.room.simplified_ui import _render_detail

    paths = _simplified_paths(tmp_path)
    room = create_room(paths)
    shell = Shell("demo-project", paths)
    with Client(page("/test-simplified-room"), request=None) as client:
        _render_detail(shell, rooms_adapter(paths), room.id)
        labels = {e._props.get("label") for e in client.elements.values()}
        tab_labels = {e._props.get("label") for e in client.elements.values()
                      if type(e).__name__ == "Tab"}

    for field in ("Room number", "Room name", "Building", "Floor", "Room type",
                  "Capacity", "Description", "Booking system", "Booking System URL override"):
        assert field in labels, f"{field!r} missing from room settings"
    assert {"Occupancy", "Settings", "Displays"} <= tab_labels


def test_render_rooms_list_flags_a_room_file_that_failed_to_parse(tmp_path):
    """The Rooms landing view (room_id=None) shows unreadable_items_banner()
    for any room file rooms_adapter() silently dropped -- not shown at all
    once a room_id is opened (that's a detail view, not the list)."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.room.backend import create_room
    from extensions.epaper.room.simplified_ui import render_rooms
    from extensions.epaper.ui.simplified_ui.layout import Shell

    paths = _simplified_paths(tmp_path)
    create_room(paths)
    (paths.room_dir / "broken.json").write_text("not json at all")
    shell = Shell("demo-project", paths)
    with Client(page("/test-rooms-broken"), request=None) as client:
        render_rooms(shell)
        labels = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}

    assert any("1 room(s) failed to load" in label for label in labels)


def test_render_rooms_with_room_id_opens_straight_to_that_rooms_detail(tmp_path):
    """The /rooms/{room_id} deep link (ui/simplified_ui/__init__.py's
    _extra_routes) passes room_id through to render_rooms(), which must open
    the DrillDownWrapper straight to that room's detail -- not the list --
    so a bookmarked/shared room URL shows the room, not the list, on load."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.room.backend import create_room
    from extensions.epaper.room.simplified_ui import render_rooms
    from extensions.epaper.ui.simplified_ui.layout import Shell

    paths = _simplified_paths(tmp_path)
    room = create_room(paths)
    shell = Shell("demo-project", paths)
    with Client(page("/test-room-deep-link"), request=None) as client:
        render_rooms(shell, room_id=room.id)
        labels = {e._props.get("label") for e in client.elements.values()}

    assert "Room number" in labels, "room_id should open the detail view directly, not the list"


def test_room_occupancy_status_shows_free_or_occupied():
    """_occupancy_status (room/simplified_ui.py) shows 'Occupied' with an
    'Until HH:MM' line when now falls inside an event, 'Free' otherwise, plus
    a 'Next'/'Then' line naming today's next event when there is one."""
    from zoneinfo import ZoneInfo

    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.global_config.backend import app_config
    from extensions.epaper.room.simplified_ui import _occupancy_status

    now = datetime.datetime.now(ZoneInfo(app_config.timezone))
    # _occupancy_status only counts a "later today" event if it's still on
    # now's own calendar date -- a fixed +2h/+3h offset would intermittently
    # cross midnight (and so fail) depending on what time the suite happens
    # to run, so scale down to a fraction of whatever time is actually left
    # before midnight instead.
    midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    remaining = midnight - now

    def _event(start_delta, end_delta, summary):
        return {"dtstart": (now + start_delta).isoformat(), "dtend": (now + end_delta).isoformat(),
                "organizer": "", "summary": summary, "categories": ""}

    current = _event(datetime.timedelta(minutes=-10), datetime.timedelta(minutes=20), "Ongoing")
    later_today = _event(remaining * 0.5, remaining * 0.75, "Later meeting")

    with Client(page("/test-occupancy-occupied"), request=None) as client:
        _occupancy_status([current, later_today])
        texts = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}
    assert "Occupied" in texts
    assert any(t.startswith("Then:") and "Later meeting" in t for t in texts)

    with Client(page("/test-occupancy-free"), request=None) as client:
        _occupancy_status([later_today])
        texts = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}
    assert "Free" in texts
    assert any(t.startswith("Next:") and "Later meeting" in t for t in texts)

    with Client(page("/test-occupancy-free-nothing-today"), request=None) as client:
        _occupancy_status([])
        texts = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}
    assert "Free" in texts
    assert "No more meetings today" in texts


def test_room_occupancy_upcoming_lists_events_with_organizer():
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.room.simplified_ui import _occupancy_upcoming

    events = [{"dtstart": "2026-09-01T10:00:00+02:00", "dtend": "2026-09-01T11:00:00+02:00",
              "organizer": "Alice", "summary": "Kickoff", "categories": ""}]

    with Client(page("/test-occupancy-upcoming"), request=None) as client:
        _occupancy_upcoming(events)
        labels = {e.text for e in client.elements.values() if type(e).__name__ == "ItemLabel"}
    assert "Kickoff" in labels
    assert any("Alice" in label for label in labels)

    with Client(page("/test-occupancy-upcoming-empty"), request=None) as client:
        _occupancy_upcoming([])
        texts = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}
    assert "No upcoming appointments." in texts


def test_room_displays_panel_shows_summary_and_bound_devices(tmp_path, monkeypatch):
    """The Displays tab leads with a room summary (room_label + type, then
    building/floor) and lists every device bound to the room, titled by
    device name with screen, panel and firmware version as subtitle."""
    import datetime
    import types

    import extensions.epaper.display.backend as display_backend
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.devicebinding.backend import set_device_binding
    from extensions.epaper.room.backend import create_room
    from extensions.epaper.room.simplified_ui import _displays_panel
    from extensions.epaper.ui.simplified_ui.layout import Shell

    paths = _simplified_paths(tmp_path)
    room = create_room(paths)
    room.room_number, room.room_name = "A-101", "North Conference"
    room.building, room.floor = "Main", "2"
    from extensions.epaper.room.backend import room_adapter
    room_adapter(paths, room.id).save(room)
    (paths.screen_dir / "weather.json").write_text('{"width": 400, "height": 300, "widgets": []}')
    set_device_binding(paths, "sign-1", room_id=room.id, screen_id="weather")

    monkeypatch.setattr(display_backend, "_project_devices", lambda project: [
        types.SimpleNamespace(name="sign-1", last_seen_at=datetime.datetime.now(datetime.timezone.utc),
                              firmware_version="1.4.2"),
    ])

    shell = Shell("demo-project", paths)
    with Client(page("/test-room-displays"), request=None) as client:
        _displays_panel(shell, room.id)
        labels = {e.text for e in client.elements.values()
                  if type(e).__name__ in ("Label", "ItemLabel")}

    assert "A-101 (North Conference) · Meeting room" in labels
    assert "Main, 2" in labels
    assert "sign-1" in labels  # list row title (device_name)
    # list row subtitle (screen_id, panel_label, firmware_version); "—" since
    # sign-1's binding has no panel_type_id set
    assert "weather · — · 1.4.2" in labels


def test_displays_top_level_lists_devices_and_shows_room_and_status(tmp_path, monkeypatch):
    """The project-wide Displays view (display/simplified_ui.py) lists every
    device (title=device_name, subtitle=room_label + screen_id) and, in the
    detail, shows the room info block, an online/last-seen line and the
    nice4iot expert link -- without needing a room_id."""
    import datetime
    import types

    import extensions.epaper.display.backend as display_backend
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.devicebinding.backend import set_device_binding
    from extensions.epaper.display.backend import RoomDisplaysAdapter
    from extensions.epaper.display.simplified_ui import render_displays, _render_detail
    from extensions.epaper.room.backend import create_room, room_adapter
    from extensions.epaper.ui.simplified_ui.layout import Shell

    paths = _simplified_paths(tmp_path)
    room = create_room(paths)
    room.room_number, room.room_name = "A-101", "North Conference"
    room_adapter(paths, room.id).save(room)
    (paths.screen_dir / "weather.json").write_text('{"width": 400, "height": 300, "widgets": []}')
    set_device_binding(paths, "sign-1", room_id=room.id, screen_id="weather")

    monkeypatch.setattr(display_backend, "_project_devices", lambda project: [
        types.SimpleNamespace(name="sign-1", last_seen_at=datetime.datetime.now(datetime.timezone.utc),
                              is_active=True, is_provisioning_approved=True),
        types.SimpleNamespace(name="sign-2", last_seen_at=None,
                              is_active=True, is_provisioning_approved=True),
    ])
    monkeypatch.setattr(display_backend, "_device_url",
                        lambda project, name: f"https://nice4iot.example/{project}/devices/{name}")

    shell = Shell("demo-project", paths)
    with Client(page("/test-displays-list"), request=None) as client:
        render_displays(shell)
        labels = {e.text for e in client.elements.values()
                  if type(e).__name__ in ("Label", "ItemLabel")}
        icons = [e for e in client.elements.values() if type(e).__name__ == "Icon"]

    assert "sign-1" in labels and "sign-2" in labels  # list row titles (device_name)
    assert "A-101 (North Conference) · weather" in labels  # sign-1's subtitle
    # a fully custom row (WiFi/battery icons) doesn't get niceview's own
    # drill-down chevron for free -- must be added by hand, one per row
    chevrons = [e for e in icons if e._props.get("name") == "chevron_right"]
    assert len(chevrons) == 2

    adapter = RoomDisplaysAdapter(paths, "demo-project")
    with Client(page("/test-displays-detail-bound"), request=None) as client:
        _render_detail(paths, "/api/screen", adapter, "sign-1")
        texts = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}
        links = [e for e in client.elements.values() if type(e).__name__ == "Link"]
    assert any("A-101 (North Conference)" in t for t in texts)
    assert any("Online" in t and "last seen" in t for t in texts)
    assert links and links[0]._props.get("href") == "https://nice4iot.example/demo-project/devices/sign-1"

    with Client(page("/test-displays-detail-unbound"), request=None) as client:
        _render_detail(paths, "/api/screen", adapter, "sign-2")
        texts = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}
    assert "Not assigned to a room" in texts
    assert any("Offline" in t and "never" in t for t in texts)


def test_display_status_key_combines_active_provisioning_and_online():
    """_status_key (display/simplified_ui.py) mirrors nice4iot's own project
    Devices grid status dot (app.core.device.backend.device_status_key):
    inactive beats everything, then pending provisioning approval, then
    plain online/offline."""
    from extensions.epaper.display.models import RoomDisplayRow
    from extensions.epaper.display.simplified_ui import _status_key

    def row(**kwargs):
        return RoomDisplayRow(device_name="d", **kwargs)

    assert _status_key(row(is_active=False, is_provisioning_approved=True, online=True)) == "inactive"
    assert _status_key(row(is_active=True, is_provisioning_approved=False, online=True)) == "pending"
    assert _status_key(row(is_active=True, is_provisioning_approved=False, online=False)) == "pending"
    assert _status_key(row(is_active=True, is_provisioning_approved=True, online=True)) == "online"
    assert _status_key(row(is_active=True, is_provisioning_approved=True, online=False)) == "offline"


def test_device_preview_with_no_screen_shows_only_the_fallback_label(tmp_path):
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.display.preview import render_device_preview

    paths = _simplified_paths(tmp_path)
    with Client(page("/test-preview-no-screen"), request=None) as client:
        render_device_preview(paths, "sign-1", None, "/api/screen")
        texts = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}
        tabs = [e for e in client.elements.values() if type(e).__name__ == "Tab"]
    assert "No screen assigned yet." in texts
    assert not tabs


def test_device_preview_with_screen_but_no_delivery_yet(tmp_path):
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.display.preview import render_device_preview

    paths = _simplified_paths(tmp_path)
    with Client(page("/test-preview-undelivered"), request=None) as client:
        render_device_preview(paths, "sign-1", "hallway", "/api/screen")
        texts = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}
        tab_labels = {e._props.get("label") for e in client.elements.values() if type(e).__name__ == "Tab"}
        images = [e for e in client.elements.values() if type(e).__name__ == "Image"]
    assert tab_labels == {"Current", "Last delivered"}
    assert "This device hasn't fetched its image yet." in texts
    # Current tab's live preview is built from image_base_url + device name,
    # forcing a fresh render, bypassing the browser cache, and excluded from
    # the "last delivered" snapshot (it's an admin preview, not a real device
    # poll -- see api/endpoints.py's _PREVIEW_DESCRIPTION)
    assert any((e._props.get("src") or "").startswith(
        "/api/screen/sign-1/image.png?force=true&preview=true&_t=") for e in images)
    # no last_delivered.png element without a snapshot on disk
    assert not any(e._props.get("src") == "/api/screen/sign-1/last_delivered.png" for e in images)


def test_device_preview_shows_the_last_delivered_snapshot_and_its_age(tmp_path):
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.devicebinding.snapshot import save_device_snapshot
    from extensions.epaper.display.preview import render_device_preview

    paths = _simplified_paths(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"fake-png-bytes")
    save_device_snapshot(paths, "sign-1", source)

    with Client(page("/test-preview-delivered"), request=None) as client:
        render_device_preview(paths, "sign-1", "hallway", "/api/screen")
        texts = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}
        images = [e for e in client.elements.values() if type(e).__name__ == "Image"]
    assert any(t.startswith("Delivered ") for t in texts)
    assert any(e._props.get("src") == "/api/screen/sign-1/last_delivered.png" for e in images)


def test_display_screen_select_falls_back_when_no_screens_exist(tmp_path, monkeypatch):
    """A select widget crashes on an empty options list, so if
    available_screen_ids() ever returns [] (it no longer can from "zero
    screens in the project" alone -- the auto-generated Room Calendar
    templates, screen.backend.synthetic_roomcalendar_screens, always give at
    least one -- but the guard stays for a hypothetically empty panel-type
    catalog too) both the top-level and room-scoped display details must
    fall back to a plain hinted field instead of an empty select."""
    import types

    import extensions.epaper.display.backend as display_backend
    import extensions.epaper.display.simplified_ui as display_simplified_ui
    import extensions.epaper.room.simplified_ui as room_simplified_ui
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.devicebinding.backend import set_device_binding
    from extensions.epaper.display.backend import RoomDisplaysAdapter
    from extensions.epaper.display.simplified_ui import _render_detail as top_level_detail
    from extensions.epaper.room.backend import create_room
    from extensions.epaper.room.simplified_ui import _display_detail
    from extensions.epaper.ui.simplified_ui.layout import Shell

    paths = _simplified_paths(tmp_path)
    room = create_room(paths)
    set_device_binding(paths, "sign-1", room_id=room.id)
    monkeypatch.setattr(display_backend, "_project_devices", lambda project: [
        types.SimpleNamespace(name="sign-1", last_seen_at=None)])
    monkeypatch.setattr(display_simplified_ui, "available_screen_ids", lambda paths, device_name: [])
    monkeypatch.setattr(room_simplified_ui, "available_screen_ids", lambda paths, device_name: [])

    adapter = RoomDisplaysAdapter(paths, "demo-project")
    with Client(page("/test-no-screens-top-level"), request=None) as client:
        top_level_detail(paths, "/api/screen", adapter, "sign-1")
        hints = {e._props.get("hint") for e in client.elements.values()}
    assert "No screens yet — add one in Templates" in hints

    shell = Shell("demo-project", paths)
    room_adapter = RoomDisplaysAdapter(paths, "demo-project", room.id)
    with Client(page("/test-no-screens-room"), request=None) as client:
        _display_detail(shell, room_adapter, "sign-1", lambda new_key: None)
        hints = {e._props.get("hint") for e in client.elements.values()}
    assert "No screens yet — add one in Templates" in hints


def test_available_screen_ids_always_offers_synthetic_templates(tmp_path):
    """With zero real screen files, available_screen_ids() still offers the
    auto-generated Room Calendar templates -- the empty-project case is no
    longer reachable through it (see the fallback test above)."""
    from extensions.epaper.display.backend import available_screen_ids

    paths = _simplified_paths(tmp_path)
    ids = available_screen_ids(paths, "sign-1")
    assert ids, "the built-in panel catalog should yield at least one template"
    assert all(i.startswith("__roomcalendar_") for i in ids)


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


def test_rooms_project_tab_create_dialog_survives_no_booking_systems(tmp_path):
    """With zero booking systems configured, niceview resolves the modelselect
    repository to options={} -- and its own select widget then treats that
    falsy dict as "no options defined" and raises. The Add/Edit dialog builds
    its form the same way (ModelForm.from_item + with_repositories), so
    rooms_wrapper() must not register an empty repository, or opening the
    dialog on a fresh install (no booking systems yet) crashes."""
    from nicegui.client import Client
    from nicegui.page import page
    from niceview import ModelForm

    from extensions.epaper.room.models import RoomModel
    from extensions.epaper.room.ui import rooms_wrapper

    paths = _simplified_paths(tmp_path)
    wrapper = rooms_wrapper(paths, "demo-project")

    with Client(page("/test-rooms-create-dialog"), request=None) as client:
        form = ModelForm.from_item(RoomModel())
        if wrapper._model_repositories:
            form.with_repositories(wrapper._model_repositories)
        form.render()  # must not raise ValueError("... has no options ...")
        assert client.elements


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


def test_booking_system_header_editor_lists_entries_with_round_add_and_delete(tmp_path):
    """Booking system detail's header editor (bookingsystem/ui.py):
    an inline-editable list -- every row a live Header/Value ui.input pair
    (not static text), no dialog to add or change one -- with a delete icon
    per row and an Add button matching DrillDownWrapper's own toolbar style
    (dense round -- see main.py's niceview.set_chrome_style(
    toolbar_icon_button_props=...))."""
    from nicegui.client import Client
    from nicegui.elements.input import Input
    from nicegui.page import page

    from extensions.epaper.bookingsystem.backend import booking_systems_adapter, create_booking_system
    from extensions.epaper.bookingsystem.ui import _header_editor

    paths = _simplified_paths(tmp_path)
    adapter = booking_systems_adapter(paths)
    system = create_booking_system(paths)
    system.header = {"X-Api-Key": "secret123", "Accept": "text/calendar"}
    adapter.update(system)

    with Client(page("/test-booking-header-editor"), request=None) as client:
        _header_editor(adapter, system.id)
        input_values = {e.value for e in client.elements.values() if isinstance(e, Input)}
        buttons = [e for e in client.elements.values() if type(e).__name__ == "Button"]
        dialogs = [e for e in client.elements.values() if type(e).__name__ == "Dialog"]

    assert {"X-Api-Key", "secret123", "Accept", "text/calendar"} <= input_values
    assert not dialogs  # rows are live inputs -- nothing to pop open

    delete_buttons = [b for b in buttons if b._props.get("icon") == "delete"]
    assert len(delete_buttons) == 2
    for b in delete_buttons:
        assert b._props.get("round") and b._props.get("color") == "negative"

    add_buttons = [b for b in buttons if b._props.get("icon") == "add"]
    assert len(add_buttons) == 1
    assert add_buttons[0]._props.get("dense") and add_buttons[0]._props.get("round")


def test_booking_system_header_editor_shows_placeholder_when_empty(tmp_path):
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.bookingsystem.backend import booking_systems_adapter, create_booking_system
    from extensions.epaper.bookingsystem.ui import _header_editor

    paths = _simplified_paths(tmp_path)
    adapter = booking_systems_adapter(paths)
    system = create_booking_system(paths)
    system.header = {}
    adapter.update(system)

    with Client(page("/test-booking-header-editor-empty"), request=None) as client:
        _header_editor(adapter, system.id)
        labels = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}

    assert "No custom headers." in labels


def test_booking_system_category_color_editor_lists_entries(tmp_path):
    """Booking system detail's category-color editor (bookingsystem/ui.py):
    an inline-editable list -- every row a live Category ui.input plus a
    swatch picker (not static text), no dialog to add or change one -- same
    shape as the header editor above."""
    from nicegui.client import Client
    from nicegui.elements.input import Input
    from nicegui.page import page

    from extensions.epaper.bookingsystem.backend import booking_systems_adapter, create_booking_system
    from extensions.epaper.bookingsystem.ui import _category_color_editor

    paths = _simplified_paths(tmp_path)
    adapter = booking_systems_adapter(paths)
    system = create_booking_system(paths)
    system.category_colors = {"Lecture": "#ff0000", "Exam": "#0000ff"}
    adapter.update(system)

    with Client(page("/test-booking-category-color-editor"), request=None) as client:
        _category_color_editor(paths, adapter, system.id)
        input_values = {e.value for e in client.elements.values() if isinstance(e, Input)}
        buttons = [e for e in client.elements.values() if type(e).__name__ == "Button"]
        dialogs = [e for e in client.elements.values() if type(e).__name__ == "Dialog"]

    assert {"Lecture", "Exam"} <= input_values
    assert not dialogs  # rows are live inputs -- nothing to pop open
    delete_buttons = [b for b in buttons if b._props.get("icon") == "delete"]
    assert len(delete_buttons) == 2


def test_booking_system_category_color_editor_shows_placeholder_when_empty(tmp_path):
    from nicegui.client import Client
    from nicegui.elements.label import Label
    from nicegui.page import page

    from extensions.epaper.bookingsystem.backend import booking_systems_adapter, create_booking_system
    from extensions.epaper.bookingsystem.ui import _category_color_editor

    paths = _simplified_paths(tmp_path)
    adapter = booking_systems_adapter(paths)
    system = create_booking_system(paths)

    with Client(page("/test-booking-category-color-editor-empty"), request=None) as client:
        _category_color_editor(paths, adapter, system.id)
        labels = {e.text for e in client.elements.values() if isinstance(e, Label)}

    assert "No category colors." in labels


def test_six_color_palette_id_resolves_to_the_spectra_e6_colors(tmp_path):
    """bookingsystem/ui.py's category-color picker is restricted to
    _SIX_COLOR_PALETTE_ID -- a typo/renamed id here would silently fall back
    to the unrestricted ui.color_input path instead of failing loudly."""
    from extensions.epaper.bookingsystem.ui import _SIX_COLOR_PALETTE_ID
    from extensions.epaper.catalog.backend import get_palette

    paths = _simplified_paths(tmp_path)
    palette = get_palette(_SIX_COLOR_PALETTE_ID, paths)
    assert palette is not None
    assert set(palette.palette) == {
        (0, 0, 0), (255, 255, 255), (255, 255, 0), (255, 0, 0), (0, 0, 255), (0, 255, 0),
    }


def test_simplified_schedule_creates_and_edits_the_default_schedule(tmp_path):
    """Preferences > Schedule (schedule/simplified_ui.py) auto-creates
    default.json on first visit and renders schedule/ui.py's rule-cards
    editor for it directly -- no list/rename/delete chrome, since there is
    only ever one schedule here."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.schedule.simplified_ui import DEFAULT_SCHEDULE_FILENAME, render_schedule
    from extensions.epaper.ui.simplified_ui.layout import Shell

    paths = _simplified_paths(tmp_path)
    shell = Shell("demo-project", paths)

    with Client(page("/test-simplified-schedule"), request=None) as client:
        render_schedule(shell)
        labels = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}
        button_texts = {e.text for e in client.elements.values() if type(e).__name__ == "Button"}

    assert (paths.schedule_dir / DEFAULT_SCHEDULE_FILENAME).is_file()
    assert "Schedule" in labels
    assert "No weekly rules yet — add one below." in labels
    assert "Add Rule" in button_texts


def test_schedule_rule_card_has_an_add_times_button(tmp_path):
    """Each weekly rule card offers a '+' next to Times to bulk-add times in
    a range, in both the simplified and non-simplified editor (same
    schedule_editor_content); by_weekdays/by_months carry a restriction
    hint so an unfamiliar user can tell what unchecking an entry does."""
    from nicegui.client import Client
    from nicegui.page import page
    from niceview import JsonListAdapter

    from extensions.epaper.schedule.models import WeeklyScheduleModel
    from extensions.epaper.schedule.ui import schedule_editor_content
    from extensions.epaper.paths import EpaperPaths

    paths = EpaperPaths(root=tmp_path)
    paths.ensure_dirs()
    schedule_path = paths.schedule_dir / "default.json"
    JsonListAdapter(WeeklyScheduleModel, schedule_path).create(WeeklyScheduleModel(times=["08:00"]))

    with Client(page("/test-schedule-rule-card"), request=None) as client:
        schedule_editor_content(paths, "default.json")
        tooltips = {e.text for e in client.elements.values() if type(e).__name__ == "Tooltip"}
        labels = {e._props.get("label") for e in client.elements.values()}
        texts = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}

    assert "Add times in a range" in tooltips
    assert "Only on these weekdays" in labels or "Only on these weekdays" in texts
    assert "Only in these months" in labels or "Only in these months" in texts


def test_times_in_range_used_by_add_times_dialog():
    """The dialog's own math (times_in_range + set-union merge) matches what
    a user adding a lunch-hours range on top of an existing morning time
    would expect -- guards the merge/sort/dedup behavior schedule/ui.py's
    add_times_in_range relies on, without driving the async dialog itself."""
    from extensions.epaper.schedule.backend import times_in_range

    existing = ["08:00"]
    new_times = times_in_range("12:00", "13:00", 30)
    merged = sorted(set(existing) | set(new_times))
    assert merged == ["08:00", "12:00", "12:30", "13:00"]


def test_room_booking_select_lists_configured_systems(tmp_path):
    """A room's booking_system_id is a select of the configured systems: its
    options come from storage, not the model, and include each system by name."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.bookingsystem.backend import booking_systems_adapter, create_booking_system
    from extensions.epaper.room.backend import rooms_adapter, create_room
    from extensions.epaper.ui.simplified_ui.layout import Shell
    from extensions.epaper.room.simplified_ui import _render_detail

    paths = _simplified_paths(tmp_path)
    system = create_booking_system(paths)
    system.name = "iCal Uni"
    booking_systems_adapter(paths).update(system)
    room = create_room(paths)
    shell = Shell("demo-project", paths)
    with Client(page("/test-room-booking-select"), request=None) as client:
        _render_detail(shell, rooms_adapter(paths), room.id)
        selects = [e for e in client.elements.values()
                   if e._props.get("label") == "Booking system"]

    assert selects, "no 'Booking system' select rendered"
    option_labels = {o.get("label") for o in selects[0]._props.get("options", [])}
    assert "iCal Uni" in option_labels


def test_standalone_global_tab_links_to_the_simplified_ui():
    """The Global tab shows the 'Rooms & Displays App' card (above the
    settings card) that navigates to the standalone simplified-UI route."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.ui.standalone import SIMPLIFIED_ROUTE, _simplified_ui_link

    with Client(page("/test-simplified-link"), request=None) as client:
        _simplified_ui_link()
        texts = {e.text for e in client.elements.values()
                 if type(e).__name__ in ("Label", "Button")}

    assert "Rooms & Displays App" in texts and "Open" in texts
    assert SIMPLIFIED_ROUTE == "/simplified"
