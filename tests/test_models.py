import pytest
from pydantic import ValidationError
from extensions.epaper.models.screenmodel import (
    ScreenModel, TextWidgetModel, RoomCalendarWidgetModel,
    WeatherNowWidgetModel, WeatherForecastWidgetModel, WeatherChartWidgetModel,
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


def test_widget_font_none_when_either_part_missing():
    widget = TextWidgetModel(position_x=0, position_y=0, text="x", font_name="Ubuntu-Regular.ttf")
    assert widget.font is None
    widget.font_size = 16
    assert widget.font == ("Ubuntu-Regular.ttf", 16)


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


def test_weather_now_widget_requires_coordinates():
    with pytest.raises(ValidationError):
        WeatherNowWidgetModel(position_x=0, position_y=0)
    widget = WeatherNowWidgetModel(position_x=0, position_y=0, latitude=52.52, longitude=13.405)
    assert widget.latitude == 52.52


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
