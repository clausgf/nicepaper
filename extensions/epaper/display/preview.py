"""
Current / Last delivered preview tabs for a device's Display Detail --
shared by room/simplified_ui.py's per-room Displays tab and
display/simplified_ui.py's project-wide Displays list, both of which drill
into the same kind of row (a device bound to a screen).

Current is a live preview, same idea as the screen editor's own preview.
Last delivered is the frozen PNG a device's own alias URL actually served
last with a real 200 OK, plus when (devicebinding/snapshot.py) -- it can lag
behind Current if the device hasn't polled recently or missed a delivery,
which is the point of showing both.
"""
import datetime
from typing import Optional

from nicegui import ui

from extensions.epaper.devicebinding.snapshot import read_device_snapshot
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.util import humanize_age


def render_device_preview(paths: EpaperPaths, device_name: str,
                          screen_id: Optional[str], image_base_url: str) -> None:
    if not screen_id:
        ui.label('No screen assigned yet.').classes('text-caption text-grey')
        return

    with ui.tabs().classes('w-full') as tabs:
        current_tab = ui.tab('current', label='Current')
        delivered_tab = ui.tab('delivered', label='Last delivered')
    with ui.tab_panels(tabs, value=current_tab).classes('w-full'):
        with ui.tab_panel(current_tab):
            # device_name, not screen_id: resolves through the device's own
            # binding (devicebinding/backend.py), so a room-aware
            # auto-generated template (e.g. RoomCalendar) renders for this
            # device's own room, same as the device's real alias URL would.
            #
            # force=true + a unique timestamp: opening this preview must
            # show a genuinely fresh render (e.g. after a settings change
            # that a widget reads live but that doesn't touch the screen's
            # config mtime), not whatever the cache or the browser happen
            # to still have.
            cache_bust = datetime.datetime.now(datetime.timezone.utc).timestamp()
            ui.image(f'{image_base_url}/{device_name}/image.png?force=true&_t={cache_bust}').classes('w-full')
        with ui.tab_panel(delivered_tab):
            snapshot = read_device_snapshot(paths, device_name)
            if snapshot is None:
                ui.label("This device hasn't fetched its image yet.").classes('text-caption text-grey')
                return
            now = datetime.datetime.now(datetime.timezone.utc)
            ui.label(f'Delivered {humanize_age(snapshot.fetched_at, now)}').classes('text-caption text-grey')
            ui.image(f'{image_base_url}/{device_name}/last_delivered.png').classes('w-full')
