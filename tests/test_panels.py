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


def test_default_widgets_have_no_empty_required_fields():
    """A newly added widget must validate as a whole: niceview enforces
    required fields at the widget level and commits an item only once it
    validates, so an empty required string (the old placeholder) would block
    every other edit in the widget's form until it is filled in."""
    from extensions.epaper.ui.screen_editor import WIDGET_MODELS, _default_widget
    for widget_type, model_cls in WIDGET_MODELS.items():
        widget = _default_widget(widget_type)
        assert isinstance(widget, model_cls)
        empty = [name for name, field in model_cls.model_fields.items()
                 if field.is_required() and getattr(widget, name) in (None, '', [])]
        assert not empty, f"{widget_type} starts with empty required field(s): {empty}"


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
    from extensions.epaper.ui.panels import global_config_fields

    with Client(page("/test-global-config"), request=None) as client:
        global_config_fields(persist=lambda: None)
        labels = {e._props.get("label") for e in client.elements.values()}

    # a field from each section, so a silently dropped group is noticed too
    for expected in ("Locale", "Font name", "Color accent", "Latitude",
                     "Weather error", "Home Assistant URL"):
        assert expected in labels, f"{expected!r} missing from the global settings card"

    # every setting should have a widget; none may be skipped silently
    assert len([e for e in labels if e]) >= len(GlobalConfig.model_fields)
