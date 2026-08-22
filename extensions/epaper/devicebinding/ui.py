"""
The per-device settings card nice4iot embeds in its own device page
(register_device_card in extensions/epaper/__init__.py).

Renders content only -- no ui.card()/ui.expansion() of its own, since nice4iot
supplies one -- so it looks like nice4iot's built-in cards (see docs/extensions.md
in the nice4iot repo).
"""
from nicegui import context, ui

from extensions.epaper.devicebinding.backend import get_device_binding, set_device_binding
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.room.backend import list_rooms


def device_config_card(paths: EpaperPaths, device_name: str, image_base_url: str) -> None:
    """
    'general' device settings card content.

    Lets the admin assign this device a screen (the image it renders) and a
    room (where it hangs). Both are stored in the device binding
    (devicebinding/backend.py) keyed by the device's own name -- so the
    device-specific image URL shown below is just the normal screen image
    endpoint addressed by device name instead of screen id: the device only
    ever needs to know its own name, never any screen id, and every existing
    query parameter/header (If-None-Match, ...) keeps working unchanged since
    it's the same route.

    The room assignment is the device->room half of the same relation the
    simplified UI reads back as "the displays in a room" (see
    devicebinding.backend.devices_in_room), so a device is navigable from a room
    and vice versa.
    """
    screen_names = sorted(p.stem for p in paths.screen_dir.glob('*.json'))
    # {id: label} so the select shows the room's label, not its surrogate id
    room_options = {r.id: r.room_label for r in list_rooms(paths)}
    binding = get_device_binding(paths, device_name)

    base_url = str(context.client.request.base_url).rstrip('/')
    image_url = f'{base_url}{image_base_url}/{device_name}/image.png'

    def on_screen_change(e) -> None:
        set_device_binding(paths, device_name, screen_id=e.value)
        ui.notify('Saved', type='positive')

    def on_room_change(e) -> None:
        set_device_binding(paths, device_name, room_id=e.value)
        ui.notify('Saved', type='positive')

    ui.label('Assign a screen to this device to give it its own image URL below, '
             'and the room it is mounted in.').classes('text-caption')
    if binding.screen_id and binding.screen_id not in screen_names:
        ui.label(f'Assigned screen "{binding.screen_id}" no longer exists.').classes('text-caption text-negative')
    if binding.room_id and binding.room_id not in room_options:
        ui.label('Assigned room no longer exists.').classes('text-caption text-negative')

    ui.select(
        screen_names,
        value=binding.screen_id if binding.screen_id in screen_names else None,
        label='Screen',
        clearable=True,
        on_change=on_screen_change,
    ).classes('w-full').props('outlined dense')

    ui.select(
        room_options,
        value=binding.room_id if binding.room_id in room_options else None,
        label='Room',
        clearable=True,
        on_change=on_room_change,
    ).classes('w-full').props('outlined dense')

    with ui.row().classes('w-full items-center gap-2 q-mt-sm'):
        ui.input(label='Image URL', value=image_url).props('outlined dense readonly').classes('flex-grow')
        ui.button(icon='content_copy').props('dense flat') \
            .tooltip('Copy the URL').on_click(lambda: ui.clipboard.write(image_url))
