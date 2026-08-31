from .base import Widget
from .text import TextWidget
from .date import DateWidget
from .box import BoxWidget
from .line import LineWidget
from .roomcalendar import RoomCalendarWidget
from .weather import WeatherNowWidget, WeatherForecastWidget, WeatherChartWidget
from .image import ImageWidget
from .homeassistant import HomeAssistantWidget

# What draws a widget of each type, looked up by Screen (screen/backend.py).
# A table rather than the getattr(widgets, widget_type + "Widget") this used
# to be: the naming convention was invisible from either end, and a typo in
# a widget_type resolved to None at render time instead of being a missing
# key here. The editor's side of the same question -- icon, title, form --
# is ui/widget_types.py; both are keyed by the widget_type literal in
# screen/models.py.
WIDGET_CLASSES: dict[str, type[Widget]] = {
    "Text": TextWidget,
    "Date": DateWidget,
    "Box": BoxWidget,
    "Line": LineWidget,
    "RoomCalendar": RoomCalendarWidget,
    "WeatherNow": WeatherNowWidget,
    "WeatherForecast": WeatherForecastWidget,
    "WeatherChart": WeatherChartWidget,
    "Image": ImageWidget,
    "HomeAssistant": HomeAssistantWidget,
}

__all__ = [
    "Widget", "WIDGET_CLASSES",
    "TextWidget", "DateWidget", "BoxWidget", "LineWidget", "RoomCalendarWidget",
    "WeatherNowWidget", "WeatherForecastWidget", "WeatherChartWidget",
    "ImageWidget", "HomeAssistantWidget",
]
