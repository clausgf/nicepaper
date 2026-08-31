"""GlobalConfig editing form."""
from typing import Callable

from nicegui import ui
from niceview import Field, ModelForm

from extensions.epaper.config import resource_paths
from extensions.epaper.global_config.backend import app_config

_LAYOUT = [
    ['## General', ['locale', 'timezone'], ['date_format', 'time_format']],
    ['## Font', ['font_name', 'font_size']],
    ['## Booking System for Room Calendar',
     ['ical_retry_min_s', 'ical_retry_max_s'],
     'ical_error',
     ['current_appointment', 'no_appointments'],
     ['next_appointment', 'further_appointments'],
     ['roomcalendar_date_format_long', 'roomcalendar_date_format_short',
      'roomcalendar_time_format']],
    ['## Weather',
     ['weather_update_interval_s', 'weather_retry_min_s', 'weather_retry_max_s', 'wind_speed_unit:w-24'],
     ['weather_error', 'weather_stale_notice']],
    ['## Image', ['image_retry_min_s', 'image_retry_max_s'], 'image_error'],
    ['## Home Assistant',
     ['homeassistant_update_interval_s', 'homeassistant_retry_min_s', 'homeassistant_retry_max_s'],
     ['homeassistant_error', 'homeassistant_stale_notice']],
]


def global_config_fields(persist: Callable[[], None]) -> None:
    """Render the shared config fields without surrounding chrome."""
    font_names = sorted(p.name for p in resource_paths.font_path.glob('*') if p.is_file())
    field_infos = {
        'font_name': Field(widget_type='ui.select', options=font_names),
    }
    ModelForm.from_item(app_config, layout=_LAYOUT, field_infos=field_infos,
                        on_change=lambda e: persist()).render()


def global_config_card(persist: Callable[[], None]) -> None:
    """Render standalone config fields in a card."""
    with ui.card().classes('w-full'):
        ui.label('E-Paper Global Settings').classes('text-subtitle1')
        global_config_fields(persist)
