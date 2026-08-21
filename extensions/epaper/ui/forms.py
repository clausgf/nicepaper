"""
The form vocabulary every editor in this extension shares: how a field is
styled, how a layout group is spaced, and the hints for fields nobody can
guess from the label alone.

Field styling is set once per form via niceview's `base_props` /
`default_classes` rather than per call site, so a form here is a layout
plus the handful of field_infos that differ -- see the module docstrings
of screen/ui.py, widget_types.py and global_settings.py.
"""
from typing import Any

from niceview import Field

# Applied to every field of every form here: `props` are additive per key
# (a field can still change one of them), `classes` are only a fallback
# for a field that brings none of its own.
FORM_STYLE: dict[str, Any] = {'base_props': 'outlined dense', 'default_classes': 'w-full'}

# Layout-group prefixes. ':classes' replaces a container's defaults, and
# these panels have always been tighter than niceview's gap-4. COL stacks,
# ROW puts fields side by side, ROW_CENTER is for a row mixing fields of
# different heights (a toggle next to an input).
COL = ':w-full gap-2'
ROW = ':w-full items-start gap-2'
ROW_CENTER = ':w-full items-center gap-3'

# Short hints for fields whose value is unguessable without help:
# Babel/CLDR patterns, the two-letter alignment code, the '{time}'
# placeholder of the stale-data notices. A field's description is a
# tooltip (niceview's default), which a touch device can't show, so these
# sit permanently below the widget on top of the full description.
DATE_PATTERN_HINT = 'CLDR pattern, e.g. EEEE, dd. MMMM yyyy'
SHORT_DATE_PATTERN_HINT = 'CLDR pattern, e.g. dd.MM.yy'
TIME_PATTERN_HINT = 'CLDR pattern, e.g. HH:mm'
STALE_NOTICE_HINT = "'{time}' is replaced by the last successful update"
ALIGNMENT_HINT = 'Horizontal l/c/r + vertical t/c/b'
# the fallback is all-or-nothing (see WeatherWidgetModel.resolved_location),
# so the hint says "both", not "empty = default" per field
LOCATION_HINT = 'Both empty = default location'


def hints(**field_hints: str) -> dict[str, Any]:
    """{'field_name': Field(hint=...)} for several fields at once, for
    merging into a form's `field_infos`."""
    return {name: Field(hint=hint) for name, hint in field_hints.items()}
