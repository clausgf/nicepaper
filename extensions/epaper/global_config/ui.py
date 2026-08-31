"""
The GlobalConfig editing form: one layout plus the field_infos that differ
from the defaults, in place of the ~90 hand-placed render_field() calls
this used to be.

The layout also fixes the order the fields appear in, which the model
itself does not: GlobalConfig groups its fields by subsystem (iCal,
weather, Home Assistant), while the card leads with the settings a user
actually looks for first.
"""
from typing import Callable

from nicegui import ui
from niceview import Field, ModelForm

from extensions.epaper.config import resource_paths
from extensions.epaper.global_config.backend import app_config
from extensions.epaper.ui.forms import (
    COL, DATE_PATTERN_HINT, FORM_STYLE, HOMEASSISTANT_ERROR_HINT, ROW, SHORT_DATE_PATTERN_HINT,
    STALE_NOTICE_HINT, TIME_PATTERN_HINT, hints,
)

# Curated CLDR patterns for the date/time ui.select fields below --
# with_input=True keeps them editable, so any other CLDR pattern still works.
_SHORT_DATE_FORMATS = ['dd.MM.yy', 'dd.MM.yyyy', 'yyyy-MM-dd', 'MM/dd/yy', 'MM/dd/yyyy', 'dd/MM/yyyy']
_LONG_DATE_FORMATS = ['EEEE, dd.MM.yyyy', 'EEEE, dd. MMMM yyyy', 'EEEE, MMMM d, yyyy', 'yyyy-MM-dd']
_TIME_FORMATS = ['HH:mm', 'HH:mm:ss', 'hh:mm a', 'h:mm a']

_LAYOUT = [
    ['## General', COL, [ROW, 'locale', 'timezone'], [ROW, 'date_format', 'time_format']],
    ['## Font & Colors', COL,
     [ROW, 'font_name', 'font_size'],
     [ROW, 'color_background', 'color_primary', 'color_accent']],
    ['## iCal (Room Calendar)', COL,
     'ical_error',
     [ROW, 'ical_retry_min_s', 'ical_retry_max_s'],
     [ROW, 'no_appointments', 'next_appointment'],
     [ROW, 'current_appointment', 'further_appointments'],
     [ROW, 'roomcalendar_date_format_long', 'roomcalendar_date_format_short',
      'roomcalendar_time_format']],
    ['## Weather', COL,
     [ROW, 'weather_update_interval_s', 'wind_speed_unit'],
     [ROW, 'weather_retry_min_s', 'weather_retry_max_s'],
     [ROW, 'weather_error', 'weather_stale_notice']],
    ['## Image', COL, 'image_error', [ROW, 'image_retry_min_s', 'image_retry_max_s']],
    ['## Home Assistant', COL,
     [ROW, 'homeassistant_update_interval_s', 'homeassistant_retry_min_s',
      'homeassistant_retry_max_s'],
     [ROW, 'homeassistant_error', 'homeassistant_stale_notice']],
]


def _field_infos() -> dict:
    font_names = sorted(p.name for p in resource_paths.font_path.glob('*') if p.is_file())
    return {
        'font_name': Field(widget_type='ui.select', options=font_names),
        'wind_speed_unit': Field(widget_type='ui.select', options=['kmh', 'ms', 'mph', 'kn']),
        'date_format': Field(widget_type='ui.select', options=_SHORT_DATE_FORMATS, with_input=True),
        'time_format': Field(widget_type='ui.select', options=_TIME_FORMATS, with_input=True),
        'roomcalendar_date_format_long': Field(widget_type='ui.select', options=_LONG_DATE_FORMATS, with_input=True),
        'roomcalendar_date_format_short': Field(widget_type='ui.select', options=_SHORT_DATE_FORMATS, with_input=True),
        'roomcalendar_time_format': Field(widget_type='ui.select', options=_TIME_FORMATS, with_input=True),
        'color_background': Field(widget_type='ui.color_input'),
        'color_primary': Field(widget_type='ui.color_input'),
        'color_accent': Field(widget_type='ui.color_input'),
        # explicit labels: the humanized field names would all read
        # "Homeassistant ..." (one word, wrong spelling) and repeat the
        # section heading in every field
        'ical_retry_min_s': Field(label='iCal retry min s'),
        'ical_retry_max_s': Field(label='iCal retry max s'),
        'image_retry_min_s': Field(label='Image retry min s'),
        'image_retry_max_s': Field(label='Image retry max s'),
        'homeassistant_update_interval_s': Field(label='Update interval s'),
        'homeassistant_retry_min_s': Field(label='Retry min s'),
        'homeassistant_retry_max_s': Field(label='Retry max s'),
        'homeassistant_error': Field(label='Error message', hint=HOMEASSISTANT_ERROR_HINT),
        'homeassistant_stale_notice': Field(label='Stale notice', hint=STALE_NOTICE_HINT),
        **hints(date_format=SHORT_DATE_PATTERN_HINT, time_format=TIME_PATTERN_HINT,
                roomcalendar_date_format_long=DATE_PATTERN_HINT,
                roomcalendar_date_format_short=SHORT_DATE_PATTERN_HINT,
                roomcalendar_time_format=TIME_PATTERN_HINT,
                weather_stale_notice=STALE_NOTICE_HINT),
    }


def global_config_fields(persist: Callable[[], None]) -> None:
    """
    The GlobalConfig editing fields, no ui.card()/ui.expansion() of their
    own -- nice4iot's register_global_card('E-Paper', ...) wraps this in
    its own uniform config_expansion(title) (see docs/extensions.md in the
    nice4iot repo: 'general'/global cards must render only their fields,
    not their own chrome, so third-party cards match nice4iot's built-in
    ones). global_config_card() below adds a plain ui.card() around this
    for standalone, which has no such chrome to rely on.

    ModelForm.from_item binds directly to the shared GlobalConfig
    singleton, app_config -- not a fresh copy from an adapter -- so
    autosave edits mutate app_config's own attributes in place: every
    module that already did `from extensions.epaper.global_config.backend
    import app_config` sees the changes without needing to change anything.
    `persist()` is the caller's job (write to the right JSON path for
    standalone vs. the nice4iot extension); this function doesn't know or
    care which.
    """
    ModelForm.from_item(app_config, layout=_LAYOUT, field_infos=_field_infos(),
                        on_change=lambda e: persist(), **FORM_STYLE).render()


def global_config_card(persist: Callable[[], None]) -> None:
    """Standalone-only wrapper around global_config_fields(): standalone
    has no nice4iot chrome to supply a card/heading, so this builds its
    own -- see global_config_fields()'s docstring for why nice4iot's own
    register_global_card() usage (extensions/epaper/__init__.py) calls
    global_config_fields() directly instead of this."""
    with ui.card().classes('w-full'):
        ui.label('E-Paper Global Settings').classes('text-subtitle1')
        global_config_fields(persist)
