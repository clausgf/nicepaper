from .base import Widget
from .text import TextWidget
from .date import DateWidget
from .roomcalendar import RoomCalendarWidget
from .weather import WeatherNowWidget, WeatherForecastWidget, WeatherChartWidget
from .image import ImageWidget
from .homeassistant import HomeAssistantWidget

# What draws a widget of each type, looked up by Screen (core/screen.py).
# A table rather than the getattr(widgets, widget_type + "Widget") this used
# to be: the naming convention was invisible from either end, and a typo in
# a widget_type resolved to None at render time instead of being a missing
# key here. The editor's side of the same question -- icon, title, form --
# is ui/widget_types.py; both are keyed by the widget_type literal in
# models/screenmodel.py.
WIDGET_CLASSES: dict[str, type[Widget]] = {
    "Text": TextWidget,
    "Date": DateWidget,
    "RoomCalendar": RoomCalendarWidget,
    "WeatherNow": WeatherNowWidget,
    "WeatherForecast": WeatherForecastWidget,
    "WeatherChart": WeatherChartWidget,
    "Image": ImageWidget,
    "HomeAssistant": HomeAssistantWidget,
}

__all__ = [
    "Widget", "WIDGET_CLASSES",
    "TextWidget", "DateWidget", "RoomCalendarWidget",
    "WeatherNowWidget", "WeatherForecastWidget", "WeatherChartWidget",
    "ImageWidget", "HomeAssistantWidget",
]
