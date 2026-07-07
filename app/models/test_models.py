import pytest
from pydantic import ValidationError
from .screenmodel import ScreenModel, TextWidgetModel, RoomCalendarWidgetModel


def test_screen_model_valid():
    valid_data = {
        "size": [400, 300],
        "widgets": [
            {
                "widget_type": "Text",
                "position": [0, 0],
                "size": [100, 200],
                "text": "Welcome to the main screen"
            },
            {
                "widget_type": "RoomCalendar",
                "position": [1, 1],
                "size": [300, 400],
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
    assert isinstance(screen.widgets[1], RoomCalendarWidgetModel)


def test_screen_model_missing_size():
    with pytest.raises(ValidationError):
        ScreenModel(widgets=[])


def test_screen_model_invalid_widget_type():
    invalid_data = {
        "size": [400, 300],
        "widgets": [
            {
                "position": [0, 0],
                "size": [100, 200],
                "widget_type": "InvalidType",
                "text": "Welcome to the main screen"
            }
        ]
    }
    with pytest.raises(ValidationError):
        ScreenModel(**invalid_data)


def test_screen_model_missing_widget_type():
    invalid_data = {
        "size": [400, 300],
        "widgets": [
            {
                "position": [0, 0],
                "size": [100, 200],
            }
        ]
    }
    with pytest.raises(ValidationError) as exc_info:
        ScreenModel(**invalid_data)
    assert "widget_type" in str(exc_info.value)


def test_screen_model_textwidget_missing_text():
    invalid_data = {
        "size": [400, 300],
        "widgets": [
            {
                "widget_type": "Text",
                "position": [0, 0],
                "size": [100, 200],
            }
        ]
    }
    with pytest.raises(ValidationError) as exc_info:
        ScreenModel(**invalid_data)
    assert "field required" in str(exc_info.value).lower()


def test_widget_alignment_pattern():
    base = {
        "widget_type": "Text",
        "position": [0, 0],
        "text": "x",
    }
    assert TextWidgetModel(**base, alignment="ct").alignment == "ct"
    with pytest.raises(ValidationError):
        TextWidgetModel(**base, alignment="xx")
