import pytest
from pydantic import ValidationError
from extensions.epaper.screen.models import (
    ScreenModel, TextWidgetModel, RoomCalendarWidgetModel,
    WeatherNowWidgetModel, WeatherForecastWidgetModel, WeatherChartWidgetModel,
    ImageWidgetModel, HomeAssistantWidgetModel,
)


def test_screen_model_valid():
    valid_data = {
        "width": 400,
        "height": 300,
        "widgets": [
            {
                "widget_type": "Text",
                "position_x": 0,
                "position_y": 0,
                "size_width": 100,
                "size_height": 200,
                "text": "Welcome to the main screen"
            },
            {
                "widget_type": "RoomCalendar",
                "position_x": 1,
                "position_y": 1,
                "size_width": 300,
                "size_height": 400,
                "room_number": "101",
                "room_name": "Conference Room",
                "ical_url": "http://example.com/calendar.ics"
            }
        ]
    }
    screen = ScreenModel(**valid_data)
    assert screen.size == (400, 300)
    assert len(screen.widgets) == 2
    assert isinstance(screen.widgets[0], TextWidgetModel)
    assert screen.widgets[0].position == (0, 0)
    assert screen.widgets[0].size == (100, 200)
    assert isinstance(screen.widgets[1], RoomCalendarWidgetModel)


def test_screen_model_missing_size():
    with pytest.raises(ValidationError):
        ScreenModel(widgets=[])


def test_widget_size_both_set_or_both_empty_is_valid():
    fixed = TextWidgetModel(position_x=0, position_y=0, size_width=100, size_height=200, text="x")
    assert fixed.size == (100, 200)
    auto = TextWidgetModel(position_x=0, position_y=0, text="x")
    assert auto.size is None
    # a cleared ui.number round-trips as 0, which counts as automatic too
    zeroed = TextWidgetModel(position_x=0, position_y=0, size_width=0, size_height=0, text="x")
    assert zeroed.size is None


@pytest.mark.parametrize("width,height", [(200, None), (None, 300), (200, 0), (0, 300)])
def test_widget_half_set_size_is_rejected(width, height):
    with pytest.raises(ValidationError, match="together"):
        TextWidgetModel(position_x=0, position_y=0,
                        size_width=width, size_height=height, text="x")


def test_screen_model_invalid_widget_type():
    invalid_data = {
        "width": 400,
        "height": 300,
        "widgets": [
            {
                "position_x": 0,
                "position_y": 0,
                "size_width": 100,
                "size_height": 200,
                "widget_type": "InvalidType",
                "text": "Welcome to the main screen"
            }
        ]
    }
    with pytest.raises(ValidationError):
        ScreenModel(**invalid_data)


def test_screen_model_missing_widget_type():
    invalid_data = {
        "width": 400,
        "height": 300,
        "widgets": [
            {
                "position_x": 0,
                "position_y": 0,
                "size_width": 100,
                "size_height": 200,
            }
        ]
    }
    with pytest.raises(ValidationError) as exc_info:
        ScreenModel(**invalid_data)
    assert "widget_type" in str(exc_info.value)


def test_screen_model_textwidget_missing_text():
    invalid_data = {
        "width": 400,
        "height": 300,
        "widgets": [
            {
                "widget_type": "Text",
                "position_x": 0,
                "position_y": 0,
                "size_width": 100,
                "size_height": 200,
            }
        ]
    }
    with pytest.raises(ValidationError) as exc_info:
        ScreenModel(**invalid_data)
    assert "field required" in str(exc_info.value).lower()


def test_widget_size_none_when_either_dimension_missing():
    widget = TextWidgetModel(position_x=0, position_y=0, text="x")
    assert widget.size is None
    widget.size_width = 100
    assert widget.size is None
    widget.size_height = 50
    assert widget.size == (100, 50)


def test_widget_size_setter():
    widget = TextWidgetModel(position_x=0, position_y=0, text="x")
    widget.size = (10, 20)
    assert widget.size_width == 10
    assert widget.size_height == 20
    widget.size = None
    assert widget.size_width is None
    assert widget.size_height is None


def test_widget_size_zero_means_automatic_too():
    """niceview's ui.number has no clean 'empty' state for Optional[int]:
    clearing the field in the browser round-trips as 0, not None. 0 must
    behave exactly like unset, or auto-sizing silently breaks the moment
    a user touches the field without typing a replacement value. (A
    half-set size -- only one of width/height -- is a validation error, see
    test_widget_half_set_size_is_rejected.)"""
    widget = TextWidgetModel(position_x=0, position_y=0, text="x", size_width=0, size_height=0)
    assert widget.size is None
    widget = TextWidgetModel(position_x=0, position_y=0, text="x", size_width=100, size_height=50)
    assert widget.size == (100, 50)


def test_widget_resolved_font_falls_back_per_aspect():
    default = ("Ubuntu-Regular.ttf", 16)
    # only the name overridden -> keeps the default size
    only_name = TextWidgetModel(position_x=0, position_y=0, text="x", font_name="Ubuntu-Bold.ttf")
    assert only_name.resolved_font(*default) == ("Ubuntu-Bold.ttf", 16)
    # only the size overridden -> keeps the default name
    only_size = TextWidgetModel(position_x=0, position_y=0, text="x", font_size=30)
    assert only_size.resolved_font(*default) == ("Ubuntu-Regular.ttf", 30)
    # neither set (None or the 0 a cleared ui.number sends) -> both defaults
    neither = TextWidgetModel(position_x=0, position_y=0, text="x", font_name=None, font_size=0)
    assert neither.resolved_font(*default) == default
    # both set -> both overridden
    both = TextWidgetModel(position_x=0, position_y=0, text="x", font_name="Ubuntu-Bold.ttf", font_size=30)
    assert both.resolved_font(*default) == ("Ubuntu-Bold.ttf", 30)


def test_widget_alignment_pattern():
    base = {
        "widget_type": "Text",
        "position_x": 0,
        "position_y": 0,
        "text": "x",
    }
    assert TextWidgetModel(**base, alignment="ct").alignment == "ct"
    with pytest.raises(ValidationError):
        TextWidgetModel(**base, alignment="xx")


def test_weather_now_widget_coordinates_are_optional():
    """They used to be required; an empty pair now means "use the default
    location from the global settings"."""
    assert WeatherNowWidgetModel(position_x=0, position_y=0).latitude is None
    widget = WeatherNowWidgetModel(position_x=0, position_y=0, latitude=52.52, longitude=13.405)
    assert widget.latitude == 52.52


def test_weather_location_falls_back_as_a_pair():
    def location(**coords):
        return WeatherNowWidgetModel(position_x=0, position_y=0, **coords).resolved_location(52.52, 13.405)

    assert location(latitude=48.14, longitude=11.58) == (48.14, 11.58), "own location wins"
    assert location() == (52.52, 13.405), "no location at all -> the default"
    # a cleared ui.number round-trips as 0, so a zero pair is "empty" too
    assert location(latitude=0.0, longitude=0.0) == (52.52, 13.405)
    # ... but half a location must not be completed from the global setting,
    # which would put the widget somewhere neither setting describes
    assert location(latitude=48.14) == (48.14, 0.0)
    assert location(longitude=11.58) == (0.0, 11.58)


def test_weather_location_is_none_when_nothing_is_configured():
    widget = WeatherNowWidgetModel(position_x=0, position_y=0)
    assert widget.resolved_location(0.0, 0.0) is None


def test_weather_forecast_widget_default_forecast_hours():
    widget = WeatherForecastWidgetModel(position_x=0, position_y=0, latitude=52.52, longitude=13.405)
    assert widget.forecast_hours == 24


def test_weather_chart_widget_defaults():
    widget = WeatherChartWidgetModel(position_x=0, position_y=0, latitude=52.52, longitude=13.405)
    assert widget.primary_metric == "temperature"
    assert widget.secondary_metric is None
    assert widget.forecast_hours == 24


def test_weather_chart_widget_invalid_metric_rejected():
    with pytest.raises(ValidationError):
        WeatherChartWidgetModel(position_x=0, position_y=0, latitude=52.52, longitude=13.405,
                                 primary_metric="not_a_metric")


def test_weather_chart_widget_combined_metrics():
    widget = WeatherChartWidgetModel(position_x=0, position_y=0, latitude=52.52, longitude=13.405,
                                      primary_metric="precipitation", secondary_metric="temperature")
    assert widget.primary_metric == "precipitation"
    assert widget.secondary_metric == "temperature"


def test_weather_chart_widget_accepts_wind_metric():
    widget = WeatherChartWidgetModel(position_x=0, position_y=0, latitude=52.52, longitude=13.405,
                                      primary_metric="wind", secondary_metric="temperature")
    assert widget.primary_metric == "wind"


def test_image_widget_defaults():
    w = ImageWidgetModel(position_x=0, position_y=0)
    assert w.source_type == "url"
    assert w.url is None and w.file is None
    assert w.reload_each_time is False


@pytest.mark.parametrize("kwargs", [
    {"size_width": 100},                  # only width -> keep aspect ratio
    {"size_height": 50},                  # only height -> keep aspect ratio
    {"size_width": 100, "size_height": 50},  # both -> exact
    {},                                   # neither -> natural size
])
def test_image_widget_allows_partial_size(kwargs):
    # unlike other widgets, the Image widget opts out of the size-pair check
    w = ImageWidgetModel(position_x=0, position_y=0, **kwargs)
    assert w.size_width == kwargs.get("size_width")
    assert w.size_height == kwargs.get("size_height")


def test_image_widget_round_trips_through_union():
    screen = ScreenModel(width=400, height=300, widgets=[
        {"widget_type": "Image", "position_x": 0, "position_y": 0,
         "source_type": "file", "file": "logo.png", "size_width": 120},
    ])
    assert isinstance(screen.widgets[0], ImageWidgetModel)
    reloaded = ScreenModel.model_validate_json(screen.model_dump_json())
    assert isinstance(reloaded.widgets[0], ImageWidgetModel)
    assert reloaded.widgets[0].file == "logo.png"
    assert reloaded.widgets[0].size_height is None


@pytest.mark.parametrize("widget_type,model_cls,extra", [
    ("WeatherNow", WeatherNowWidgetModel, {}),
    ("WeatherForecast", WeatherForecastWidgetModel, {}),
    ("WeatherChart", WeatherChartWidgetModel, {"primary_metric": "precipitation", "secondary_metric": "temperature"}),
])
def test_weather_widget_discriminated_union_round_trip(widget_type, model_cls, extra):
    screen = ScreenModel(width=400, height=300, widgets=[
        {"widget_type": widget_type, "position_x": 0, "position_y": 0, "latitude": 52.52, "longitude": 13.405, **extra},
    ])
    assert isinstance(screen.widgets[0], model_cls)
    reloaded = ScreenModel.model_validate_json(screen.model_dump_json())
    assert isinstance(reloaded.widgets[0], model_cls)
    if extra:
        assert reloaded.widgets[0].primary_metric == "precipitation"
        assert reloaded.widgets[0].secondary_metric == "temperature"


def test_homeassistant_widget_defaults():
    w = HomeAssistantWidgetModel(position_x=0, position_y=0, entity_id="sensor.temp")
    assert w.display == "value" and w.gauge_style == "arc"
    assert w.attribute is None and w.label is None and w.unit is None
    assert w.decimals == 1 and w.show_label is True
    assert (w.min_value, w.max_value) == (0.0, 100.0)


def test_homeassistant_widget_requires_an_entity_id():
    with pytest.raises(ValidationError):
        HomeAssistantWidgetModel(position_x=0, position_y=0)


def test_homeassistant_widget_rejects_unknown_display_and_gauge_style():
    with pytest.raises(ValidationError):
        HomeAssistantWidgetModel(position_x=0, position_y=0, entity_id="sensor.temp", display="dial")
    with pytest.raises(ValidationError):
        HomeAssistantWidgetModel(position_x=0, position_y=0, entity_id="sensor.temp", gauge_style="needle")


def test_homeassistant_widget_round_trips_through_union():
    screen = ScreenModel(width=400, height=300, widgets=[
        {"widget_type": "HomeAssistant", "position_x": 10, "position_y": 20,
         "entity_id": "sensor.living_room_temperature", "display": "gauge",
         "gauge_style": "bar", "min_value": -10, "max_value": 40, "decimals": 0},
    ])
    assert isinstance(screen.widgets[0], HomeAssistantWidgetModel)
    reloaded = ScreenModel.model_validate_json(screen.model_dump_json())
    widget = reloaded.widgets[0]
    assert isinstance(widget, HomeAssistantWidgetModel)
    assert widget.entity_id == "sensor.living_room_temperature"
    assert (widget.display, widget.gauge_style) == ("gauge", "bar")
    assert (widget.min_value, widget.max_value, widget.decimals) == (-10.0, 40.0, 0)


# --- RoomModel (simplified UI) ---------------------------------------------

def test_room_model_defaults_are_valid_and_serialize_as_default_content():
    from extensions.epaper.room.models import RoomModel
    room = RoomModel()
    # every field has a default, so a fresh room is valid and its JSON is the
    # default_content a newly added room is created from
    assert room.room_number and room.room_name and room.room_type == "meeting"
    assert RoomModel.model_validate_json(room.model_dump_json()) == room


def test_room_model_rejects_unknown_room_type():
    from extensions.epaper.room.models import RoomModel
    with pytest.raises(ValidationError):
        RoomModel(room_type="broom-closet")


@pytest.mark.parametrize("url", ["", "http://x/c.ics", "https://x/c.ics", "webcal://x/c.ics"])
def test_room_model_accepts_empty_or_calendar_urls(url):
    from extensions.epaper.room.models import RoomModel
    assert RoomModel(booking_ical_url=url).booking_ical_url == url


def test_room_model_rejects_non_calendar_ical_url():
    from extensions.epaper.room.models import RoomModel
    with pytest.raises(ValidationError):
        RoomModel(booking_ical_url="ftp://host/cal.ics")


def test_room_id_is_generated_unique_and_stable():
    from extensions.epaper.room.models import RoomModel
    a, b = RoomModel(), RoomModel()
    assert a.id and b.id and a.id != b.id  # each room gets its own surrogate id
    # an explicit id is preserved (round-trip), not regenerated
    fixed = RoomModel(id="fixed-id-123")
    assert RoomModel.model_validate_json(fixed.model_dump_json()).id == "fixed-id-123"
    # renaming never touches the id
    renamed = fixed.model_copy(update={"room_name": "New Name", "room_number": "Z-999"})
    assert renamed.id == "fixed-id-123"


def test_room_type_labels_cover_every_type_including_lecture_and_seminar():
    import typing
    from extensions.epaper.room.models import ROOM_TYPE_LABELS, RoomType
    assert set(ROOM_TYPE_LABELS) == set(typing.get_args(RoomType))
    assert {"lecture", "seminar"} <= set(ROOM_TYPE_LABELS)


def test_room_capacity_is_optional_and_non_negative():
    from extensions.epaper.room.models import RoomModel
    assert RoomModel().capacity is None
    assert RoomModel(capacity=0).capacity == 0
    with pytest.raises(ValidationError):
        RoomModel(capacity=-1)


def test_room_fields_carry_niceview_field_info_for_the_form():
    """The form metadata lives on the model: niceview's FieldInfo rides each
    field's Annotated metadata (the UI passes no per-field field_infos except
    the runtime booking-system options)."""
    from niceview import FieldInfo
    from extensions.epaper.room.models import RoomModel
    for name in ("room_type", "capacity", "photo", "description",
                 "booking_system_id", "booking_ical_url"):
        md = RoomModel.model_fields[name].metadata
        assert any(isinstance(m, FieldInfo) for m in md), f"{name} has no niceview FieldInfo"
