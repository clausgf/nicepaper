from typing import Optional, Union

from extensions.epaper.config import app_config
from extensions.epaper.core import charting
from extensions.epaper.core.datasources.weather import get_weather, weather_icon_and_description
from extensions.epaper.models.screenmodel import (
    WeatherForecastWidgetModel, WeatherNowWidgetModel,
    WeatherPrecipitationWidgetModel, WeatherTemperatureWidgetModel,
)
from extensions.epaper.util import logger
from ..drawingcontext import DrawingContext
from .base import Widget

AnyWeatherWidgetModel = Union[
    WeatherNowWidgetModel, WeatherForecastWidgetModel,
    WeatherPrecipitationWidgetModel, WeatherTemperatureWidgetModel,
]

_DEFAULT_SIZE = (300, 150)


class _WeatherWidgetBase(Widget):
    """Shared setup for the four weather widgets: a default size (like
    RoomCalendarWidget's) and the try/except-and-draw-error pattern around
    the datasource fetch, matching the just-established convention in
    RoomCalendarWidget.draw()."""

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
            ctx.draw_text((0, 0), size=(w, h), text=app_config.weather_error,
                          font=ctx.get_font("Ubuntu-Regular.ttf", 16))
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
        icon_font = ctx.get_font("fa-solid-900.ttf", int(icon_size * 0.8))
        temp_font = ctx.get_font("Ubuntu-Bold.ttf", max(14, h // 3))
        desc_font = ctx.get_font("Ubuntu-Regular.ttf", max(10, h // 7))

        ctx.draw_text((0, 0), size=(icon_size, h), text=icon, alignment='cc', font=icon_font)

        info_x = icon_size
        info_w = max(0, w - icon_size)
        temp_text = f"{current['temperature_2m']:.0f}°C"
        ctx.draw_text((info_x, 0), size=(info_w, h // 2), text=temp_text, alignment='lc', font=temp_font)
        ctx.draw_text((info_x, h // 2), size=(info_w, h // 4), text=description,
                      alignment='lt', font=desc_font, ellipsis='...')
        wind_text = f"Wind {current['wind_speed_10m']:.0f} km/h"
        ctx.draw_text((info_x, h - h // 4), size=(info_w, h // 4), text=wind_text,
                      alignment='lb', font=desc_font, ellipsis='...')


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
        max_columns = max(1, w // 40)
        indices = [i for i in range(start_idx, len(times), hour_step)
                   if i < start_idx + self.config.forecast_hours][:max_columns]
        if not indices:
            return

        col_w = w / len(indices)
        icon_h = int(h * 0.5)
        row_h = (h - icon_h) // 2
        # font sizes must fit the actual box height, not just column width --
        # a font sized off col_w alone can overflow a short row vertically
        icon_font = ctx.get_font("fa-solid-900.ttf", max(10, int(min(col_w, icon_h) * 0.8)))
        temp_font = ctx.get_font("Ubuntu-Regular.ttf", max(8, int(row_h * 0.7)))
        hour_font = ctx.get_font("Ubuntu-Regular.ttf", max(8, int(row_h * 0.6)))
        for col, idx in enumerate(indices):
            x = int(col * col_w)
            icon, _ = weather_icon_and_description(codes[idx], bool(is_days[idx]))
            hour_label = times[idx][11:16]
            ctx.draw_text((x, 0), size=(int(col_w), icon_h), text=icon, alignment='cc', font=icon_font)
            ctx.draw_text((x, icon_h), size=(int(col_w), row_h), text=f"{temps[idx]:.0f}°",
                          alignment='ct', font=temp_font)
            ctx.draw_text((x, h - row_h), size=(int(col_w), row_h), text=hour_label,
                          alignment='cb', font=hour_font)


class WeatherPrecipitationWidget(_WeatherWidgetBase):

    def __init__(self, id: str, config: WeatherPrecipitationWidgetModel):
        super().__init__(id, config)

    async def draw(self, ctx: DrawingContext):
        await super().draw(ctx)
        w, h = self.config.size
        data = await self._fetch(ctx)
        if data is None:
            return

        hourly = data["hourly"]
        times, precipitation = hourly["time"], hourly["precipitation"]
        now_iso = data["current"]["time"]
        start_idx = next((i for i, t in enumerate(times) if t >= now_iso), 0)
        end_idx = min(start_idx + self.config.forecast_hours, len(times))

        values = precipitation[start_idx:end_idx]
        labels = [times[i][11:13] for i in range(start_idx, end_idx)]
        charting.draw_bar_chart(ctx, (0, 0), (w, h), values, labels=labels)


class WeatherTemperatureWidget(_WeatherWidgetBase):

    def __init__(self, id: str, config: WeatherTemperatureWidgetModel):
        super().__init__(id, config)

    async def draw(self, ctx: DrawingContext):
        await super().draw(ctx)
        w, h = self.config.size
        data = await self._fetch(ctx)
        if data is None:
            return

        hourly = data["hourly"]
        times, temps = hourly["time"], hourly["temperature_2m"]
        now_iso = data["current"]["time"]
        start_idx = next((i for i, t in enumerate(times) if t >= now_iso), 0)
        end_idx = min(start_idx + self.config.forecast_hours, len(times))

        values = temps[start_idx:end_idx]
        labels = [times[i][11:13] for i in range(start_idx, end_idx)]
        series = [charting.ChartSeries(values)]
        charting.draw_line_chart(ctx, (0, 0), (w, h), series, labels=labels)
