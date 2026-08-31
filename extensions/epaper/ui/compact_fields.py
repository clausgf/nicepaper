"""
Compact, recurring widget-editor fields that niceview's ModelForm can't
render on its own -- its layout system dispatches strictly on a closed
WidgetType Literal (see niceview/fieldinfo.py), with no per-field custom
render hook. These are hand-built NiceGUI controls instead, the same escape
hatch WidgetType.extra already uses (ui/widget_types.py) and
bookingsystem/ui.py's swatch-list editors are the closest existing
precedent -- read the current value in, call on_change with the new one,
and let the caller write it back through its own adapter + persist().

Both stay small on purpose (a single square button) so the widget-editor
form doesn't grow one full-width row per recurring setting.
"""
from typing import Callable, List, Optional

from nicegui import ui

_SWATCH_SIZE = 'width:28px;height:28px;min-width:28px'


def compact_color_field(*, label: str, value: str, palette_hex: Optional[List[str]],
                        on_change: Callable[[str], None]) -> None:
    """A small color swatch showing `value`; click opens a menu of
    `palette_hex` (the current panel's palette -- so only colors it can
    actually display are offered) to pick from.

    Falls back to a plain, unrestricted ui.color_input when palette_hex is
    None (no palette selected for this screen -- nothing to restrict to)."""
    if palette_hex is None:
        ui.color_input(label, value=value, on_change=lambda e: on_change(e.value or value)) \
            .props('outlined dense').classes('w-full')
        return

    with ui.button().props('flat dense unelevated').style(
            f'{_SWATCH_SIZE};background-color:{value};border:1px solid #8888') \
            .tooltip(f'{label}: {value}'):
        with ui.menu().props('anchor="bottom left" self="top left"'):
            with ui.row().classes('items-center gap-1 p-2 flex-wrap').style('max-width:220px'):
                for hex_color in palette_hex:
                    ui.button().props('flat dense unelevated').style(
                        f'width:24px;height:24px;min-width:24px;background-color:{hex_color};'
                        'border:1px solid #8888') \
                        .tooltip(hex_color).on_click(lambda _, c=hex_color: on_change(c))


def compact_font_field(*, resolved_name: str, resolved_size: int,
                       default_name: str, default_size: int,
                       font_name: Optional[str], font_size: Optional[int],
                       font_options: List[str],
                       on_save: Callable[[Optional[str], Optional[int]], None]) -> None:
    """A small square font icon; click opens a dialog to pick a Font Name
    (from font_options) and a Size, or clear either back to the
    screen/global default (default_name/default_size -- the fallback
    regardless of any override, shown in the dialog's caption; kept
    distinct from resolved_name/resolved_size, the button's own tooltip,
    for the same reason compact_color_field keeps `default` separate from
    `resolved`)."""
    async def open_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes('min-w-72 gap-2'):
            ui.label('Font').classes('text-subtitle1')
            name_select = ui.select(font_options, label='Font name', value=font_name, clearable=True) \
                .props('outlined dense').classes('w-full')
            size_input = ui.number(label='Size', value=font_size, min=1, precision=0) \
                .props('outlined dense clearable').classes('w-full')
            ui.label(f'Default: {default_name}, {default_size}pt').classes('text-caption text-grey')
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=lambda: dialog.submit(False)).props('flat')
                ui.button('Save', on_click=lambda: dialog.submit(True)).props('unelevated')
        if await dialog:
            size = int(size_input.value) if size_input.value else None
            on_save(name_select.value or None, size)

    ui.button(icon='text_fields').props('flat dense unelevated').style(_SWATCH_SIZE) \
        .tooltip(f'Font: {font_name or f"default ({resolved_name})"}, '
                f'{font_size or f"default ({resolved_size})"}pt') \
        .on_click(open_dialog)
