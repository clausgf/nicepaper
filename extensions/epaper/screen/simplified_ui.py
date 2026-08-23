"""
Templates section: the simplified UI's name for screens (a room's door sign
is laid out from a "template" -- the unsimplified editor's own vocabulary,
screen/ui.py, is unaffected).

Read-only: every screen in paths.screen_dir (whichever UI created it, this
one or the non-simplified editor -- they share the same storage) plus the
auto-generated "Room Calendar WxH palette" templates (one per distinct
panel-catalog resolution/palette, see screen/backend.py's
synthetic_roomcalendar_screens), each as a card with a thumbnail preview.
Clicking a card opens a larger preview. No Add/Edit/Delete here -- that
still lives in the non-simplified editor (screen/ui.py's screens_wrapper);
this section is for browsing what's available and what it looks like.
"""
from niceview import JsonAdapter

from nicegui import ui

from extensions.epaper.paths import EpaperPaths
from extensions.epaper.screen.backend import (
    SYNTHETIC_ROOMCALENDAR_PREFIX, panel_label, synthetic_roomcalendar_label,
    synthetic_roomcalendar_screens,
)
from extensions.epaper.screen.models import ScreenModel
from extensions.epaper.ui.preview import screen_image_view
from extensions.epaper.ui.simplified_ui.common import view_header
from extensions.epaper.ui.simplified_ui.layout import Shell
from extensions.epaper.util import logger


def _real_screens(paths: EpaperPaths) -> list[tuple[str, ScreenModel]]:
    """Every screen file, skipping one that fails to parse rather than
    breaking the whole list -- same tolerance as list_rooms()/
    list_booking_systems()."""
    screens = []
    for p in sorted(paths.screen_dir.glob('*.json')):
        try:
            screens.append((p.stem, JsonAdapter(ScreenModel, p, create_if_not_exist=False).read()))
        except Exception as e:
            logger.warning(f"Skipping unreadable screen {p}: {e}")
    return screens


def render_templates(shell: Shell) -> None:
    with view_header('Templates'):
        pass
    ui.label('Every screen available for a device, and a preview of what it renders. '
            'Add or edit one in Settings (nice4iot project tab) or the standalone editor.') \
        .classes('text-caption text-grey')

    paths = shell.paths
    real = _real_screens(paths)
    synthetic = synthetic_roomcalendar_screens(paths)

    if not real and not synthetic:
        ui.label('No screens yet.').classes('italic text-grey')
        return

    with ui.row().classes('w-full gap-4'):
        for screen_id, config in real:
            _template_card(shell, screen_id, config, panel_label(config, paths))
        for screen_id, config in synthetic.items():
            _template_card(shell, screen_id, config,
                           synthetic_roomcalendar_label(config.width, config.height, config.palette_id or ''))


def _template_card(shell: Shell, screen_id: str, config: ScreenModel, label: str) -> None:
    url = f'{shell.image_base_url}/{screen_id}/image.png'
    is_synthetic = screen_id.startswith(SYNTHETIC_ROOMCALENDAR_PREFIX)
    with ui.card().classes('w-64 gap-1 cursor-pointer').on('click', lambda: _open_preview(url, config, label)):
        ui.image(url).classes('w-full').props(f'ratio={config.width / config.height}')
        ui.label(label).classes('text-subtitle2')
        with ui.row().classes('items-center gap-1 text-caption text-grey'):
            ui.icon('auto_awesome' if is_synthetic else 'description').props('size=xs')
            ui.label('Auto-generated template' if is_synthetic else screen_id)


def _open_preview(url: str, config: ScreenModel, label: str) -> None:
    with ui.dialog() as dialog, ui.card().classes('min-w-[min(90vw,60rem)]'):
        ui.label(label).classes('text-subtitle1')
        screen_image_view(url, config.width, config.height)
        with ui.row().classes('w-full justify-end'):
            ui.button('Close', on_click=dialog.close).props('flat')
    dialog.open()
