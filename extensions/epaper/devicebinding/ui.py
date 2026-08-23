"""
The per-device settings card nice4iot embeds in its own device page
(register_device_card in extensions/epaper/__init__.py).

Renders content only -- no ui.card()/ui.expansion() of its own, since nice4iot
supplies one -- so it looks like nice4iot's built-in cards (see docs/extensions.md
in the nice4iot repo).
"""
from nicegui import context, ui

from extensions.epaper.catalog.backend import get_panel_type, get_panel_types
from extensions.epaper.devicebinding.backend import get_device_binding, set_device_binding
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.room.backend import list_rooms
from extensions.epaper.screen.backend import screens_matching_panel_type, synthetic_roomcalendar_screens


def device_config_card(paths: EpaperPaths, device_name: str, image_base_url: str) -> None:
    """
    'general' device settings card content.

    Lets the admin assign this device a screen (the image it renders), a
    room (where it hangs), and, optionally, its actual panel type -- which
    only restricts the Screen select to matching resolution/palette (see
    screen.backend.screens_matching_panel_type()); nothing here validates
    screen_id against it afterwards. All three are stored in the device
    binding (devicebinding/backend.py) keyed by the device's own name -- so
    the device-specific image URL shown below is just the normal screen
    image endpoint addressed by device name instead of screen id: the
    device only ever needs to know its own name, never any screen id, and
    every existing query parameter/header (If-None-Match, ...) keeps
    working unchanged since it's the same route.

    The room assignment is the device->room half of the same relation the
    simplified UI reads back as "the displays in a room" (see
    devicebinding.backend.devices_in_room), so a device is navigable from a room
    and vice versa.
    """
    # real screen files plus the auto-generated Room Calendar templates
    # (see screen/backend.py) -- both are valid ids a device can be bound to
    all_screen_names = sorted({*(p.stem for p in paths.screen_dir.glob('*.json')),
                               *synthetic_roomcalendar_screens(paths)})
    # {id: label} so the select shows the room's label, not its surrogate id
    room_options = {r.id: r.room_label for r in list_rooms(paths)}
    panel_type_options = {pt.id: pt.name for pt in get_panel_types(paths).values()}
    binding = get_device_binding(paths, device_name)

    base_url = str(context.client.request.base_url).rstrip('/')
    image_url = f'{base_url}{image_base_url}/{device_name}/image.png'

    def screen_options_for(panel_type_id) -> list[str]:
        """Every screen when no panel type is set; otherwise only the ones
        matching it, plus the currently assigned screen even if it no
        longer matches -- a mismatch stays visible rather than silently
        dropped (same dangling-reference precedent as booking_system_id,
        screen_id elsewhere)."""
        panel_type = get_panel_type(panel_type_id, paths)
        options = all_screen_names if panel_type is None else \
            sorted(screens_matching_panel_type(paths, panel_type))
        if binding.screen_id and binding.screen_id not in options:
            options = sorted([*options, binding.screen_id])
        return options

    def on_screen_change(e) -> None:
        binding.screen_id = e.value
        set_device_binding(paths, device_name, screen_id=e.value)
        ui.notify('Saved', type='positive')

    def on_room_change(e) -> None:
        set_device_binding(paths, device_name, room_id=e.value)
        ui.notify('Saved', type='positive')

    def on_panel_type_change(e) -> None:
        binding.panel_type_id = e.value
        set_device_binding(paths, device_name, panel_type_id=e.value)
        screen_select.set_options(screen_options_for(e.value))
        ui.notify('Saved', type='positive')

    ui.label('Assign a screen to this device to give it its own image URL below, '
             'the room it is mounted in, and, optionally, its panel type (restricts '
             'the Screen choices to matching resolution/palette).').classes('text-caption')
    if binding.screen_id and binding.screen_id not in all_screen_names:
        ui.label(f'Assigned screen "{binding.screen_id}" no longer exists.').classes('text-caption text-negative')
    if binding.room_id and binding.room_id not in room_options:
        ui.label('Assigned room no longer exists.').classes('text-caption text-negative')

    ui.select(
        panel_type_options,
        value=binding.panel_type_id if binding.panel_type_id in panel_type_options else None,
        label='Panel type',
        clearable=True,
        on_change=on_panel_type_change,
    ).classes('w-full').props('outlined dense')

    screen_select = ui.select(
        screen_options_for(binding.panel_type_id),
        value=binding.screen_id if binding.screen_id in all_screen_names else None,
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
