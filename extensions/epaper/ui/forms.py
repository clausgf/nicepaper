"""
The form vocabulary every editor in this extension shares: how a field is
styled and how a layout group is spaced.

Field styling is set once per form via niceview's `base_props` /
`default_classes` rather than per call site, so a form here is a layout
plus the handful of field_infos that differ -- see the module docstrings
of screen/ui.py, widget_types.py and global_settings.py. Field hints live
on the model's own Annotated niceview.Field metadata (screen/models.py).
"""
from typing import Any

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
