"""
The per-device settings and dashboard cards nice4iot embeds in its own
device page (register_device_card in extensions/epaper/__init__.py).

device_config_card() renders content only -- no ui.card()/ui.expansion() of
its own, since nice4iot supplies one for a 'settings' card (see
docs/extensions.md in the nice4iot repo). device_dashboard_card() builds its
own ui.card(), as a 'dashboard' card must.
"""
import datetime

from nicegui import context, ui

from extensions.epaper.catalog.backend import get_panel_type, get_panel_types
from extensions.epaper.devicebinding.backend import get_device_binding, set_device_binding
from extensions.epaper.display.backend import (
    device_epaper_labels, device_epaper_telemetry, panel_mismatch_hint,
)
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.room.backend import list_rooms
from extensions.epaper.screen.backend import screens_matching_panel_type, synthetic_roomcalendar_screens
from extensions.epaper.util import humanize_age


def device_config_card(paths: EpaperPaths, project_name: str, device_name: str, image_base_url: str) -> None:
    """
    'settings' device settings card content.

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

    Below the Panel type select, a hint compares it against what the
    firmware itself last reported (device_epaper_labels()'s 'panel', keyed
    to a catalog entry by PanelTypeModel.panel_id -- the manufacturer
    designation, not this catalog's own vendor+size id) -- purely
    informational, same as panel_type_id itself; nothing here overwrites
    the operator's choice automatically.
    """
    # real screen files plus the auto-generated Room Calendar templates
    # (see screen/backend.py) -- both are valid ids a device can be bound to
    all_screen_names = sorted({*(p.stem for p in paths.screen_dir.glob('*.json')),
                               *synthetic_roomcalendar_screens(paths)})
    # {id: label} so the select shows the room's label, not its surrogate id
    room_options = {r.id: r.room_label for r in list_rooms(paths)}
    panel_types = get_panel_types(paths)
    panel_type_options = {pt.id: pt.name for pt in panel_types.values()}
    binding = get_device_binding(paths, device_name)
    reported_panel = device_epaper_labels(project_name, device_name).get('panel', '')

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

    mismatch_hint = panel_mismatch_hint(paths, panel_types, binding.panel_type_id, reported_panel)
    if mismatch_hint:
        ui.label(mismatch_hint).classes('text-caption text-negative')

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


def device_dashboard_card(paths: EpaperPaths, project_name: str, device_name: str) -> None:
    """
    'dashboard' device dashboard card content -- builds its own ui.card(),
    styled like nice4iot's built-in Device status card's "System" snapshot
    section (see nice4iot's app/core/device/ui.py: _status_card()).

    Shows esp32paper's latest kind='epaper' telemetry push (device_epaper_
    telemetry() -- panel, panels, image_status, ...) with its age, plus the
    same panel-type mismatch hint the Settings card shows
    (panel_mismatch_hint()).
    """
    binding = get_device_binding(paths, device_name)
    panel_types = get_panel_types(paths)
    metrics, labels, reported_at = device_epaper_telemetry(project_name, device_name)
    mismatch_hint = panel_mismatch_hint(paths, panel_types, binding.panel_type_id, labels.get('panel', ''))

    with ui.card().tight().classes('w-full'):
        with ui.card_section().props('dense').classes('w-full'):
            ui.label('E-Paper').classes('text-subtitle1 font-bold')
            ui.separator().classes('q-mt-xs q-mb-xs')

            if not metrics and not labels:
                ui.label('No epaper telemetry reported yet.').classes('text-caption text-grey-7')
                return

            with ui.row().classes('items-center w-full gap-1'):
                ui.space()
                ui.label(f'as of {humanize_age(reported_at, datetime.datetime.now(datetime.timezone.utc))}') \
                    .classes('text-caption text-grey-7')

            with ui.grid(columns='auto 1fr').classes('grid-cols-2 gap-y-1 q-mt-xs'):
                if 'panel' in labels:
                    ui.label('Panel').classes('text-caption text-grey-7')
                    ui.label(labels['panel']).classes('text-body2')
                if 'panels' in labels:
                    ui.label('Supported panels').classes('text-caption text-grey-7')
                    ui.label(labels['panels']).tooltip(labels['panels']) \
                        .classes('text-body2 overflow-hidden text-ellipsis')
                if 'image_status' in metrics:
                    status = metrics['image_status']
                    ok = status in (200, 304)
                    ui.label('Image status').classes('text-caption text-grey-7')
                    ui.label(str(int(status))).classes(f'text-body2{"" if ok else " text-negative"}')

            if mismatch_hint:
                ui.separator().classes('q-mt-xs q-mb-xs')
                ui.label(mismatch_hint).classes('text-caption text-negative')
