"""Small presentation helpers shared by the simplified UI views.

These keep the section views (rooms.py, displays.py, booking.py) to layout
only. The views are scaffolding: they show the intended structure with a
little demo data and wire the Add/Save actions to a `not implemented yet`
notice, until the Room / Display / BookingSystem models and their storage
exist.
"""
from contextlib import contextmanager
from typing import Callable, Optional

from nicegui import ui


@contextmanager
def view_header(title: str, *, action: Optional[str] = None,
                on_action: Optional[Callable[[], None]] = None):
    """A view's top row: a title on the left and an optional primary button
    on the right (e.g. 'Add Room'). Yields so callers can drop extra
    controls into the same row (a back button, a filter, ...)."""
    with ui.row().classes('w-full items-center justify-between'):
        with ui.row().classes('items-center gap-2'):
            yield
            ui.label(title).classes('text-h5')
        if action is not None:
            ui.button(action, icon='add', on_click=on_action or todo).props('unelevated')


def todo(feature: str = '') -> None:
    """Placeholder action: this frame ships the navigation only."""
    ui.notify(f'Not implemented yet{f": {feature}" if feature else ""}', type='info')


def scaffold_note(text: str) -> None:
    """A muted banner marking still-to-be-built content, so the demo data
    below it is never mistaken for a working feature."""
    with ui.row().classes('w-full items-center gap-2 text-grey'):
        ui.icon('construction').props('size=xs')
        ui.label(text).classes('text-caption italic')
