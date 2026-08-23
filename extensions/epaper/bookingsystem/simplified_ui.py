"""
Settings > Booking systems: a niceview DrillDownWrapper over the booking
directory (booking_systems_adapter, a JsonDirectoryAdapter), so the list, Add
and Delete are niceview's; this module supplies the row and the detail -- the
BookingSystemModel form (autosaving through the adapter, its own fields laid
out via BookingSystemModel.Meta.layout) plus a hand-built editor for the one
field that layout omits: header, a dict of extra HTTP headers sent with every
feed request, shown as a two-column list (header, value) with a delete icon
per row and an "Add" button matching DrillDownWrapper's own (dense round).

A booking system is the connection/type; a room references one by id and adds
its own resource (iCal URL) in the room settings (see room/models.py).
"""
from nicegui import ui
from niceview import CollectionAdapter, DrillDownWrapper, ModelForm

from extensions.epaper.bookingsystem.backend import booking_systems_adapter
from extensions.epaper.bookingsystem.models import BookingSystemModel

from extensions.epaper.ui.simplified_ui.layout import Shell


def render_booking_systems(shell: Shell) -> None:
    adapter = booking_systems_adapter(shell.paths)
    DrillDownWrapper(
        BookingSystemModel, adapter,  # list title/description come from BookingSystemModel.Meta
        item_title_field='name',
        item_subtitle_fields=['type', 'update_interval'],
        render_detail=lambda a, key, set_key: _render_detail(a, key),
    ).render()


def _render_detail(adapter: CollectionAdapter[BookingSystemModel], key: str) -> None:
    ModelForm.from_adapter(BookingSystemModel, adapter, key, autosave=True).render()
    _header_editor(adapter, key)
    _category_color_editor(adapter, key)


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


def _category_color_editor(adapter: CollectionAdapter[BookingSystemModel], key: str) -> None:
    """RoomCalendar card color per iCal CATEGORIES entry -- same list/delete/Add
    shape as _header_editor above, but the value is a color (swatch + picker)
    instead of plain text."""
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
        with ui.dialog() as dialog, ui.card().classes('min-w-72 gap-2'):
            ui.label('Add category color').classes('text-subtitle1')
            category_input = ui.input('Category').props('outlined dense').classes('w-full')
            color_input = ui.color_input('Color', value='#3874c8').props('outlined dense').classes('w-full')
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=lambda: dialog.submit(False)).props('flat')
                ui.button('Add', on_click=lambda: dialog.submit(True)).props('unelevated')
        if not await dialog:
            return
        category = category_input.value.strip()
        if not category:
            return
        system = adapter.read(key)
        system.category_colors = {**system.category_colors, category: color_input.value}
        adapter.update(system)
        body.refresh()

    def remove(category: str) -> None:
        system = adapter.read(key)
        system.category_colors = {k: v for k, v in system.category_colors.items() if k != category}
        adapter.update(system)
        body.refresh()

    body()
