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

    from extensions.epaper.models.screenmodel import WidgetModel
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

    from extensions.epaper.models.screenmodel import WidgetModel
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
    from extensions.epaper.ui.schedule_editor import _default_rule
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

    from extensions.epaper.models.global_config import GlobalConfig
    from extensions.epaper.ui.global_settings import global_config_fields

    with Client(page("/test-global-config"), request=None) as client:
        global_config_fields(persist=lambda: None)
        labels = {e._props.get("label") for e in client.elements.values()}

    # a field from each section, so a silently dropped group is noticed too
    for expected in ("Locale", "Font name", "Color accent", "Latitude",
                     "Weather error", "Home Assistant URL"):
        assert expected in labels, f"{expected!r} missing from the global settings card"

    # every setting should have a widget; none may be skipped silently
    assert len([e for e in labels if e]) >= len(GlobalConfig.model_fields)
