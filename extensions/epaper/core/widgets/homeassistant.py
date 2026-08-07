from typing import Optional, Tuple

from babel.dates import format_datetime, get_timezone

from extensions.epaper.config import app_config
from extensions.epaper.core import gauge
from extensions.epaper.core.datasources.homeassistant import (
    EntityStatus, entity_label, entity_unit, format_value, get_entity, numeric_value, raw_value,
)
from extensions.epaper.models.screenmodel import HomeAssistantWidgetModel
from extensions.epaper.util import logger
from ..drawingcontext import DrawingContext
from .base import Widget

# default boxes per display style: a text line needs no height to speak of,
# an arc gauge needs room for the dial plus its label rows
_DEFAULT_SIZE = {'value': (200, 40), 'arc': (160, 130), 'bar': (200, 70)}


class HomeAssistantWidget(Widget):
    """Renders one Home Assistant entity: a text line ("Living room 21.4 °C")
    or a gauge drawn locally by core/gauge.py.

    Follows the weather widgets' conventions: the datasource never raises and
    keeps serving the last-known state during an outage, so the configured
    error message is only drawn when nothing at all is known; a stale value is
    marked with homeassistant_stale_notice instead of being shown as if fresh.
    """

    def __init__(self, id: str, config: HomeAssistantWidgetModel):
        super().__init__(id, config)
        self._status: Optional[EntityStatus] = None
        if not self.config.size:
            style = self.config.gauge_style if self.config.display == 'gauge' else 'value'
            self.config.size = _DEFAULT_SIZE[style]
            logger.info(f"Widget {self.id} has no size, assuming {self.config.size}")

    def _value_font(self, ctx: DrawingContext):
        """Readout font for a gauge: the widget's own font, scaled up and bold
        so the number carries the gauge (same idea as WeatherNow's headline
        temperature)."""
        return ctx.get_font("Ubuntu-Bold.ttf", max(8, round(self.font.size * 1.5)))

    def _draw_stale_notice(self, ctx: DrawingContext, size: Tuple[int, int]) -> None:
        """'as of HH:MM' marker (top-right, small) while showing a cached value
        during an outage. No-op when the value is fresh or the notice is empty."""
        status = self._status
        if status is None or status.fresh or status.last_update is None or not app_config.homeassistant_stale_notice:
            return
        when = format_datetime(status.last_update, format=app_config.time_format,
                               tzinfo=get_timezone(app_config.timezone), locale=app_config.locale)
        text = app_config.homeassistant_stale_notice.format(time=when)
        row_h = ctx.textsize(text, self.font)[1] + 2
        ctx.draw_text((0, 0), size=(size[0], row_h), text=text, alignment='rt', font=self.font, ellipsis='...')

    async def draw(self, ctx: DrawingContext):
        await super().draw(ctx)
        w, h = self.config.size

        self._status = await get_entity(ctx.paths.homeassistant_dir, self.config.entity_id)
        value = raw_value(self._status, self.config.attribute)
        if value is None:
            ctx.draw_text((0, 0), size=(w, h), text=app_config.homeassistant_error,
                          font=self.font, ellipsis='...')
            return

        label = self.config.label or entity_label(self._status, self.config.attribute)
        unit = self.config.unit if self.config.unit is not None else entity_unit(self._status, self.config.attribute)
        value_text = format_value(value, self.config.decimals)
        if unit:
            value_text = f"{value_text} {unit}"

        if self.config.display == 'gauge':
            gauge.draw_gauge(
                ctx, (0, 0), (w, h),
                value=numeric_value(value),
                min_value=self.config.min_value, max_value=self.config.max_value,
                style=self.config.gauge_style, font=self.font, value_font=self._value_font(ctx),
                label=label if self.config.show_label else None, value_text=value_text)
        else:
            text = f"{label} {value_text}" if self.config.show_label else value_text
            ctx.draw_text((0, 0), size=(w, h), text=text, alignment=self.config.alignment,
                          font=self.font, ellipsis='...')

        self._draw_stale_notice(ctx, (w, h))
