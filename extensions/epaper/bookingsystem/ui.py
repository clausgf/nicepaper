"""
Booking systems as a nice4iot project tab: a niceview DrillDownWrapper over
the booking directory (booking_systems_adapter, a JsonDirectoryAdapter), so
the list, Add and Delete are niceview's; this module supplies the row and the
detail -- the BookingSystemModel form (autosaving through the adapter, its
own fields laid out via BookingSystemModel.Meta.layout) plus a hand-built
editor for the two fields that layout omits: header (extra HTTP headers sent
with every feed request) and category_colors (RoomCalendar card color per
iCal CATEGORIES entry), each a two-column list with a delete icon per row and
an "Add" button matching DrillDownWrapper's own (dense round).

Shared with the simplified UI's Preferences > Booking systems view
(bookingsystem/simplified_ui.py), which just wraps booking_systems_wrapper()
in a Shell-bound render() -- mirrors room/ui.py::rooms_wrapper() and
screen/ui.py::screens_wrapper().
"""
from nicegui import ui
from niceview import CollectionAdapter, DrillDownWrapper, ModelForm

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
    @ui.refreshable
    def body() -> None:
        system = adapter.read(key)
        ui.label('HTTP headers').classes('text-subtitle2')
        with ui.list().props('bordered separator').classes('w-full'):
            if not system.header:
                with ui.item():
                    ui.item_label('No custom headers.').classes('italic text-grey')
            for name, value in system.header.items():
                with ui.item():
                    with ui.item_section():
                        ui.item_label(name)
                    with ui.item_section():
                        ui.item_label(value).classes('text-grey-8')
                    with ui.item_section().props('side'):
                        ui.button(icon='delete').props('dense round size=sm color=negative') \
                            .tooltip(f'Remove {name!r}') \
                            .on_click(lambda _, n=name: remove(n))
        with ui.row().classes('w-full justify-end q-mt-sm'):
            ui.button(icon='add').props('dense round').tooltip('Add header').on_click(add)

    async def add() -> None:
        with ui.dialog() as dialog, ui.card().classes('min-w-72 gap-2'):
            ui.label('Add header').classes('text-subtitle1')
            name_input = ui.input('Header').props('outlined dense').classes('w-full')
            value_input = ui.input('Value').props('outlined dense').classes('w-full')
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=lambda: dialog.submit(False)).props('flat')
                ui.button('Add', on_click=lambda: dialog.submit(True)).props('unelevated')
        if not await dialog:
            return
        name = name_input.value.strip()
        if not name:
            return
        system = adapter.read(key)
        system.header = {**system.header, name: value_input.value}
        adapter.update(system)
        body.refresh()

    def remove(name: str) -> None:
        system = adapter.read(key)
        system.header = {k: v for k, v in system.header.items() if k != name}
        adapter.update(system)
        body.refresh()

    body()


def _category_color_editor(paths: EpaperPaths, adapter: CollectionAdapter[BookingSystemModel], key: str) -> None:
    """RoomCalendar card color per iCal CATEGORIES entry -- same list/delete/Add
    shape as _header_editor above, but the value is a color (swatch + picker
    restricted to the 6-color display's own colors, see module docstring)
    instead of plain text."""
    palette = get_palette(_SIX_COLOR_PALETTE_ID, paths)
    palette_hex = [f'#{r:02x}{g:02x}{b:02x}' for r, g, b in palette.palette] if palette else []

    @ui.refreshable
    def body() -> None:
        system = adapter.read(key)
        ui.label('Category colors').classes('text-subtitle2')
        with ui.list().props('bordered separator').classes('w-full'):
            if not system.category_colors:
                with ui.item():
                    ui.item_label('No category colors.').classes('italic text-grey')
            for category, color in system.category_colors.items():
                with ui.item():
                    with ui.item_section().props('side'):
                        ui.element('div').classes('w-6 h-6 rounded').style(f'background-color: {color}')
                    with ui.item_section():
                        ui.item_label(category)
                    with ui.item_section().props('side'):
                        ui.button(icon='delete').props('dense round size=sm color=negative') \
                            .tooltip(f'Remove {category!r}') \
                            .on_click(lambda _, c=category: remove(c))
        with ui.row().classes('w-full justify-end q-mt-sm'):
            ui.button(icon='add').props('dense round').tooltip('Add category color').on_click(add)

    async def add() -> None:
        # a color not among the 6-color display's own would just get mapped
        # to black at render time anyway (roomcalendar.py's
        # _event_category_color) -- so the picker only offers exactly those,
        # falling back to an unrestricted one if the palette is unavailable
        # for some reason (a broken/missing package resource).
        state = {'color': palette_hex[0] if palette_hex else '#3874c8'}
        with ui.dialog() as dialog, ui.card().classes('min-w-72 gap-2'):
            ui.label('Add category color').classes('text-subtitle1')
            category_input = ui.input('Category').props('outlined dense').classes('w-full')
            if palette_hex:
                ui.label('Color').classes('text-caption text-grey')

                @ui.refreshable
                def swatches() -> None:
                    with ui.row().classes('items-center gap-1 flex-wrap'):
                        for hex_color in palette_hex:
                            selected = hex_color == state['color']
                            ui.button().props('flat dense unelevated').style(
                                f'width:28px;height:28px;min-width:28px;background-color:{hex_color};'
                                f'border:{"3px solid #1976d2" if selected else "1px solid #8888"}') \
                                .tooltip(hex_color).on_click(lambda _, c=hex_color: pick(c))

                def pick(c: str) -> None:
                    state['color'] = c
                    swatches.refresh()

                swatches()
            else:
                ui.color_input('Color', value=state['color'],
                               on_change=lambda e: state.update(color=e.value)) \
                    .props('outlined dense').classes('w-full')
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=lambda: dialog.submit(False)).props('flat')
                ui.button('Add', on_click=lambda: dialog.submit(True)).props('unelevated')
        if not await dialog:
            return
        category = category_input.value.strip()
        if not category:
            return
        system = adapter.read(key)
        system.category_colors = {**system.category_colors, category: state['color']}
        adapter.update(system)
        body.refresh()

    def remove(category: str) -> None:
        system = adapter.read(key)
        system.category_colors = {k: v for k, v in system.category_colors.items() if k != category}
        adapter.update(system)
        body.refresh()

    body()
