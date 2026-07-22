from typing import Optional, Union

from extensions.epaper.config import app_config
from extensions.epaper.core import charting
from extensions.epaper.core.datasources.weather import (
    convert_wind_speed, format_wind_speed, get_weather, weather_icon_and_description,
    wind_direction_label, wind_labels,
)
from extensions.epaper.models.screenmodel import (
    WeatherChartWidgetModel, WeatherForecastWidgetModel, WeatherNowWidgetModel,
)
from extensions.epaper.util import logger
from ..drawingcontext import DrawingContext
from .base import Widget

AnyWeatherWidgetModel = Union[WeatherNowWidgetModel, WeatherForecastWidgetModel, WeatherChartWidgetModel]

_DEFAULT_SIZE = (300, 150)


class _WeatherWidgetBase(Widget):
    """Shared setup for the three weather widgets: a default size (like
    RoomCalendarWidget's) and the try/except-and-draw-error pattern around
    the datasource fetch, matching the convention established in
    RoomCalendarWidget.draw(). Text is always drawn in self.font (the
    box's configured font_name/font_size, or the screen default) at a
    fixed size -- only layout (icon size, spacing, how many labels fit)
    scales with the widget's box, not the font size itself."""

    def __init__(self, id: str, config: AnyWeatherWidgetModel):
        super().__init__(id, config)
        if not self.config.size:
            self.config.size = _DEFAULT_SIZE
            logger.info(f"Widget {self.id} has no size, assuming {self.config.size}")

    async def _fetch(self, ctx: DrawingContext) -> Optional[dict]:
        w, h = self.config.size
        try:
            return await get_weather(ctx.paths.weather_dir, self.config.latitude, self.config.longitude)
        except Exception as e:
            logger.error(f"Error occurred while fetching weather data for {self.id}: {e}")
            ctx.draw_text((0, 0), size=(w, h), text=app_config.weather_error, font=self.font)
            return None


class WeatherNowWidget(_WeatherWidgetBase):

    def __init__(self, id: str, config: WeatherNowWidgetModel):
        super().__init__(id, config)

    async def draw(self, ctx: DrawingContext):
        await super().draw(ctx)
        w, h = self.config.size
        data = await self._fetch(ctx)
        if data is None:
            return

        current = data["current"]
        icon, description = weather_icon_and_description(current["weather_code"], bool(current["is_day"]))

        icon_size = min(w, h)
        icon_font = ctx.get_font("fa-solid-900.ttf", int(icon_size * 0.75))
        # the temperature reading is a headline: a fixed multiple of the
        # configured font size (not of the box), so it stays predictable
        temp_font = ctx.get_font("Ubuntu-Bold.ttf", self.font.size * 2)

        ctx.draw_text((0, 0), size=(icon_size, h), text=icon, alignment='cc', font=icon_font)

        # nudge the text block clear of the icon's right edge
        info_x = icon_size + 2
        info_w = max(0, w - info_x)
        temp_text = f"{current['temperature_2m']:.0f}°C"
        ctx.draw_text((info_x, 0), size=(info_w, h // 2), text=temp_text, alignment='lc', font=temp_font)

        # stack description + wind lines below the temperature with a line
        # height derived from the font size, so the spacing stays constant
        # instead of being spread across whatever the box height happens to be
        labels = wind_labels()
        speed, unit = format_wind_speed(current["wind_speed_10m"])
        wind_text = f"{labels['wind']} {speed} {unit} {wind_direction_label(current['wind_direction_10m'])}"
        gusts = current.get("wind_gusts_10m")
        if gusts is not None:
            gust_speed, _ = format_wind_speed(gusts)
            wind_text += f", {labels['gusts']} {gust_speed}"
        line_h = round(self.font.size * 1.3)
        y = h // 2
        for line in (description, wind_text):
            ctx.draw_text((info_x, y), size=(info_w, line_h), text=line,
                          alignment='lt', font=self.font, ellipsis='...')
            y += line_h


class WeatherForecastWidget(_WeatherWidgetBase):

    def __init__(self, id: str, config: WeatherForecastWidgetModel):
        super().__init__(id, config)

    async def draw(self, ctx: DrawingContext):
        await super().draw(ctx)
        w, h = self.config.size
        data = await self._fetch(ctx)
        if data is None:
            return

        hourly = data["hourly"]
        times, temps, codes, is_days = (
            hourly["time"], hourly["temperature_2m"], hourly["weather_code"], hourly["is_day"])
        now_iso = data["current"]["time"]
        start_idx = next((i for i, t in enumerate(times) if t >= now_iso), 0)

        hour_step = 3
        max_columns = max(1, w // 50)
        indices = [i for i in range(start_idx, len(times), hour_step)
                   if i < start_idx + self.config.forecast_hours][:max_columns]
        if not indices:
            return

        col_w = w / len(indices)
        col_gap = 4
        icon_h = int(h * 0.5)
        row_h = (h - icon_h) // 2
        icon_font = ctx.get_font("fa-solid-900.ttf", max(8, int(min(col_w - col_gap, icon_h) * 0.65)))

        # always the full "HH:MM" format, but skip some if they'd overlap
        # at the configured font size rather than shrinking/concatenating
        label_w, _ = ctx.textsize("00:00", self.font)
        label_step = charting.x_label_step(len(indices), w, min_label_width=label_w + col_gap)

        for col, idx in enumerate(indices):
            x = int(col * col_w)
            icon, _ = weather_icon_and_description(codes[idx], bool(is_days[idx]))
            ctx.draw_text((x, 0), size=(int(col_w), icon_h), text=icon, alignment='cc', font=icon_font)
            ctx.draw_text((x, icon_h), size=(int(col_w), row_h), text=f"{temps[idx]:.0f}°",
                          alignment='ct', font=self.font)
            if col % label_step == 0:
                ctx.draw_text((x, h - row_h), size=(int(col_w), row_h), text=times[idx][11:16],
                              alignment='cb', font=self.font)


_METRIC_FIELD = {
    "temperature": "temperature_2m",
    "precipitation": "precipitation",
    "humidity": "relative_humidity_2m",
    "pressure": "surface_pressure",
    "wind": "wind_speed_10m",
}
_METRIC_KIND: dict[str, charting.Kind] = {
    "temperature": "line",
    "precipitation": "bar",  # mostly-zero, bursty -- reads better as bars
    "humidity": "line",
    "pressure": "line",
    "wind": "line",
}


def _metric_series(hourly: dict, metric: str, start_idx: int, end_idx: int,
                   axis: charting.Axis) -> charting.ChartSeries:
    """One ChartSeries for a metric over [start_idx, end_idx). Open-Meteo
    delivers wind in km/h, so the 'wind' series is converted to the configured
    wind_speed_unit here (the other metrics have no unit choice)."""
    values = hourly[_METRIC_FIELD[metric]][start_idx:end_idx]
    if metric == "wind":
        values = [None if v is None else convert_wind_speed(v) for v in values]
    return charting.ChartSeries(values, kind=_METRIC_KIND[metric], axis=axis)


class WeatherChartWidget(_WeatherWidgetBase):
    """Renders primary_metric (and optionally secondary_metric) as a
    combined bar/line chart via charting.draw_chart() -- see
    WeatherChartWidgetModel's docstring for why this replaced separate
    precipitation/temperature widgets."""

    def __init__(self, id: str, config: WeatherChartWidgetModel):
        super().__init__(id, config)

    async def draw(self, ctx: DrawingContext):
        await super().draw(ctx)
        w, h = self.config.size
        data = await self._fetch(ctx)
        if data is None:
            return

        hourly = data["hourly"]
        times = hourly["time"]
        now_iso = data["current"]["time"]
        start_idx = next((i for i, t in enumerate(times) if t >= now_iso), 0)
        end_idx = min(start_idx + self.config.forecast_hours, len(times))

        series = [_metric_series(hourly, self.config.primary_metric, start_idx, end_idx, 'primary')]
        if self.config.secondary_metric:
            series.append(
                _metric_series(hourly, self.config.secondary_metric, start_idx, end_idx, 'secondary'))

        labels = [times[i][11:16] for i in range(start_idx, end_idx)]
        charting.draw_chart(ctx, (0, 0), (w, h), series, font=self.font, labels=labels)
