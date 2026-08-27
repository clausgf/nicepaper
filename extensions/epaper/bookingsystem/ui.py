"""
Booking systems as a nice4iot project tab: a niceview DrillDownWrapper over
the booking directory (booking_systems_adapter, a JsonDirectoryAdapter), so
the list, Add and Delete are niceview's; this module supplies the row and the
detail -- the BookingSystemModel form (autosaving through the adapter, its
own fields laid out via BookingSystemModel.Meta.layout) plus a hand-built
editor for the two fields that layout omits: header (extra HTTP headers sent
with every feed request) and category_colors (RoomCalendar card color per
iCal CATEGORIES entry). header is a two-column, inline-editable list (each
row is a live input pair, autosaving on change, "Add" just appends a blank
row -- no dialog; see _header_editor()'s own docstring). category_colors
follows the same inline pattern (see _category_color_editor()'s docstring).

Shared with the simplified UI's Preferences > Booking systems view
(bookingsystem/simplified_ui.py), which just wraps booking_systems_wrapper()
in a Shell-bound render() -- mirrors room/ui.py::rooms_wrapper() and
screen/ui.py::screens_wrapper().
"""
from nicegui import ui
from niceview import CollectionAdapter, ConflictError, DrillDownWrapper, ModelForm, StorageError

from extensions.epaper.bookingsystem.backend import booking_systems_adapter
from extensions.epaper.bookingsystem.models import BookingSystemModel
from extensions.epaper.catalog.backend import get_palette
from extensions.epaper.paths import EpaperPaths

# A booking system isn't tied to one screen/panel -- several rooms with
# different panels can share it -- so the category-color picker offers the
# richest color set every panel is a subset of ("the 6-color display", the
# Spectra E6 palette) rather than one screen's own. What a given panel can't
# actually show gets mapped to black at render time instead (see
# core/widgets/roomcalendar.py::_event_category_color).
_SIX_COLOR_PALETTE_ID = 'e6'


def booking_systems_wrapper(paths: EpaperPaths) -> DrillDownWrapper:
    adapter = booking_systems_adapter(paths)
    return DrillDownWrapper(
        BookingSystemModel, adapter,  # list title/description come from BookingSystemModel.Meta
        item_title_field='name',
        item_subtitle_fields=['type', 'update_interval'],
        render_detail=lambda a, key, set_key: _render_detail(paths, a, key),
    )


def _render_detail(paths: EpaperPaths, adapter: CollectionAdapter[BookingSystemModel], key: str) -> None:
    ModelForm.from_adapter(BookingSystemModel, adapter, key, autosave=True).render()
    _header_editor(adapter, key)
    _category_color_editor(paths, adapter, key)


def _header_editor(adapter: CollectionAdapter[BookingSystemModel], key: str) -> None:
    """Inline-editable header list: every row is a live Header/Value input pair
    (no dialog to add or change one), same idea as nice4iot's forwarding-rule
    cards (app/core/forwarding/ui.py). The dict has no identity of its own
    beyond its keys, so a row's identity while editing is its position in
    `rows` (a plain local list) rather than the header name — that's what
    lets "Add" append a blank, still-unnamed row without colliding with any
    other row, and what lets a row's name itself be edited/renamed in place."""
    rows: list[list[str]] = [[name, value] for name, value in adapter.read(key).header.items()]

    def _persist() -> None:
        try:
            system = adapter.read(key)
            system.header = {name.strip(): value for name, value in rows if name.strip()}
            adapter.update(system)
        except (ConflictError, StorageError) as e:
            ui.notify(str(e), color='negative')

    @ui.refreshable
    def body() -> None:
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('HTTP headers').classes('text-subtitle2')
            ui.button(icon='add').props('dense round size=sm').tooltip('Add header').on_click(add_row)
        with ui.column().classes('w-full gap-2'):
            if not rows:
                ui.label('No custom headers.').classes('italic text-grey')
            for i, pair in enumerate(rows):
                with ui.row().classes('w-full items-center gap-2 no-wrap'):
                    ui.input('Header', value=pair[0],
                             on_change=lambda e, i=i: _update_field(i, 0, e.value)) \
                        .props('outlined dense').classes('grow')
                    ui.input('Value', value=pair[1],
                             on_change=lambda e, i=i: _update_field(i, 1, e.value)) \
                        .props('outlined dense').classes('grow')
                    ui.button(icon='delete').props('dense round size=sm color=negative flat') \
                        .tooltip('Remove').on_click(lambda _, i=i: remove_row(i))

    def _update_field(i: int, field: int, value: str) -> None:
        rows[i][field] = value
        _persist()  # structure unchanged -- no body.refresh(), that would drop input focus

    def add_row() -> None:
        rows.append(['', ''])
        body.refresh()

    def remove_row(i: int) -> None:
        rows.pop(i)
        _persist()
        body.refresh()

    body()


def _category_color_editor(paths: EpaperPaths, adapter: CollectionAdapter[BookingSystemModel], key: str) -> None:
    """Inline-editable category-color list, same shape as _header_editor above:
    every row is a live Category input plus a color picker, "Add" just appends
    a blank row -- no dialog. The color picker is restricted to the 6-color
    display's own swatches (a color outside that set would just get mapped to
    black at render time anyway, see roomcalendar.py's _event_category_color),
    falling back to a free-form ui.color_input if the palette is unavailable
    for some reason (a broken/missing package resource)."""
    palette = get_palette(_SIX_COLOR_PALETTE_ID, paths)
    palette_hex = [f'#{r:02x}{g:02x}{b:02x}' for r, g, b in palette.palette] if palette else []
    rows: list[list[str]] = [[category, color] for category, color in adapter.read(key).category_colors.items()]

    def _persist() -> None:
        try:
            system = adapter.read(key)
            system.category_colors = {category.strip(): color for category, color in rows if category.strip()}
            adapter.update(system)
        except (ConflictError, StorageError) as e:
            ui.notify(str(e), color='negative')

    @ui.refreshable
    def body() -> None:
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Category colors').classes('text-subtitle2')
            ui.button(icon='add').props('dense round size=sm').tooltip('Add category color').on_click(add_row)
        with ui.column().classes('w-full gap-2'):
            if not rows:
                ui.label('No category colors.').classes('italic text-grey')
            for i, pair in enumerate(rows):
                with ui.row().classes('w-full items-center gap-2 no-wrap'):
                    ui.input('Category', value=pair[0],
                             on_change=lambda e, i=i: _update_field(i, e.value)) \
                        .props('outlined dense').classes('grow')
                    if palette_hex:
                        with ui.row().classes('items-center gap-1 flex-wrap'):
                            for hex_color in palette_hex:
                                selected = hex_color == pair[1]
                                ui.button().props('flat dense unelevated').style(
                                    f'width:28px;height:28px;min-width:28px;background-color:{hex_color};'
                                    f'border:{"3px solid #1976d2" if selected else "1px solid #8888"}') \
                                    .tooltip(hex_color).on_click(lambda _, i=i, c=hex_color: pick_color(i, c))
                    else:
                        ui.color_input('Color', value=pair[1],
                                       on_change=lambda e, i=i: pick_color(i, e.value)) \
                            .props('outlined dense').classes('grow')
                    ui.button(icon='delete').props('dense round size=sm color=negative flat') \
                        .tooltip('Remove').on_click(lambda _, i=i: remove_row(i))

    def _update_field(i: int, value: str) -> None:
        rows[i][0] = value
        _persist()  # structure unchanged -- no body.refresh(), that would drop input focus

    def pick_color(i: int, color: str) -> None:
        rows[i][1] = color
        _persist()
        body.refresh()  # swatch selection border needs to move -- no focus to lose here

    def add_row() -> None:
        rows.append(['', palette_hex[0] if palette_hex else '#3874c8'])
        body.refresh()

    def remove_row(i: int) -> None:
        rows.pop(i)
        _persist()
        body.refresh()

    body()
