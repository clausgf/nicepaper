"""
Displays: the simplified UI's flat, project-wide list of e-paper displays,
so nice4iot devices can be assigned a screen and panel type without opening
nice4iot's own device UI -- meant for people who shouldn't need to. A
display is a nice4iot device (see extensions/epaper/__init__.py,
register_device_card).

`render_displays()` builds a niceview DrillDownWrapper over
`RoomDisplaysAdapter(paths, project_name)` (no room_id -- every device in the
project, bound to a room or not): list, Add and Delete are all disabled here
(a display is a nice4iot device we neither create nor unbind from this
project-wide view; room assignment happens in the room's own Displays tab,
room/simplified_ui.py, which has its own drill-down list instead of this
one). Screen and Panel type are the only editable fields; everything else is
read-only, hand-rendered rather than through ModelForm/ModelList, so it can
show icons (status, RSSI, battery) instead of plain field values.
"""
import datetime
from typing import Optional

import niceview
from nicegui import ui
from niceview import CollectionAdapter, DrillDownWrapper, ModelForm

from extensions.epaper.catalog.backend import get_panel_types, panel_type_label
from extensions.epaper.devicebinding.backend import set_device_binding
from extensions.epaper.display.backend import (
    RoomDisplaysAdapter, available_screen_ids, panel_mismatch_hint,
)
from extensions.epaper.display.models import RoomDisplayRow
from extensions.epaper.display.preview import render_device_preview
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.simplified_ui.layout import Shell
from extensions.epaper.util import humanize_age


def render_displays(shell: Shell) -> None:
    paths, project_name = shell.paths, shell.project_name
    DrillDownWrapper(
        RoomDisplayRow, RoomDisplaysAdapter(paths, project_name),
        title='Displays',
        item_title_field='device_name',
        add_button=None, delete_button=None,
        render_list_item=_render_list_item,
        render_list_container=_render_list_container,
        render_detail=lambda a, key, set_key: _render_detail(paths, shell.image_base_url, a, key),
    ).render()


def _render_list_container(render_rows) -> None:
    with ui.list().props('bordered separator').classes('w-full'):
        render_rows()


def _render_list_item(key: str, item: RoomDisplayRow, select) -> None:
    """A fully custom row (status dot + WiFi/battery icons, which
    ModelList's default title/subtitle row has no room for) -- so unlike
    every other list in this app, it doesn't get niceview's own drill-down
    chevron for free (ModelList adds that itself; DrillDownWrapper only adds
    it when render_list_item is left unset, see niceview/modellist.py's
    list_chevron_icon). Added by hand here to match, same icon/style
    niceview's default chrome uses."""
    with ui.item(on_click=select):
        with ui.item_section().props('avatar'):
            _status_icon(item).props('size=xs')
        with ui.item_section():
            ui.item_label(item.device_name)
            subtitle = ' · '.join(v for v in (item.room_label, item.screen_id) if v)
            if subtitle:
                ui.item_label(subtitle).props('caption')
        with ui.item_section().props('side'):
            with ui.row().classes('items-center gap-2 no-wrap'):
                ui.icon(_wifi_icon(item.rssi), color='grey-7').props('size=sm').tooltip(_rssi_text(item.rssi))
                ui.icon(_battery_icon(item.battery_voltage), color=_battery_color(item.battery_voltage)) \
                    .props('size=sm').tooltip(_battery_text(item.battery_voltage))
        with ui.item_section().props('side'):
            ui.icon('chevron_right').classes('text-grey')


def _render_detail(paths: EpaperPaths, image_base_url: str,
                   adapter: CollectionAdapter[RoomDisplayRow], key: str) -> None:
    """Device name is the wrapper's own title row (item_title_field), shown
    in both list and detail already, so it isn't repeated here.

    Wrapped in a local @ui.refreshable (like room/simplified_ui.py's
    _display_detail) so changing Panel type can redraw the whole body against
    the freshly saved binding -- the Screen options (available_screen_ids())
    and the mismatch hint both depend on it."""
    panel_types = get_panel_types(paths)
    panel_type_options = {pt.id: panel_type_label(pt) for pt in panel_types.values()}

    @ui.refreshable
    def _body(current_key: str) -> None:
        item = adapter.read(current_key)
        # filtered to the device's own panel type if it has one set
        screen_ids = available_screen_ids(paths, item.device_name)

        def on_panel_type_change(e) -> None:
            set_device_binding(paths, item.device_name, panel_type_id=e.value)
            _body.refresh(current_key)

        with ui.column().classes('w-full gap-3'):
            with ui.row().classes('items-center gap-1 text-grey-7'):
                ui.icon('meeting_room').props('size=xs')
                if item.room_label:
                    ui.label(f'{item.room_label} — {item.building or "—"} / {item.floor or "—"} / {item.room_number}')
                else:
                    ui.label('Not assigned to a room')

            ui.select(
                panel_type_options,
                value=item.panel_type_id if item.panel_type_id in panel_type_options else None,
                label='Panel type',
                clearable=True,
                on_change=on_panel_type_change,
            ).classes('w-full').props('outlined dense')

            mismatch_hint = panel_mismatch_hint(paths, panel_types, item.panel_type_id, item.reported_panel)
            if mismatch_hint:
                ui.label(mismatch_hint).classes('text-caption text-negative')

            # an empty options list crashes the select widget, so fall back to a
            # plain hinted field rather than passing one.
            screen_field = (niceview.Field(widget_type='ui.select', options=screen_ids, clearable=True)
                           if screen_ids else niceview.Field(hint='No screens yet — add one in Templates'))
            ModelForm.from_adapter(RoomDisplayRow, adapter, current_key, autosave=True,
                                   include=['screen_id'],
                                   field_infos={'screen_id': screen_field},
                                   ).render()

            render_device_preview(paths, item.device_name, item.screen_id, image_base_url)

            with ui.row().classes('items-center gap-2'):
                _status_icon(item).props('size=sm')
                now = datetime.datetime.now(datetime.timezone.utc)
                ui.label(f'{_STATUS_LABELS[_status_key(item)]} · last seen {humanize_age(item.last_seen_at, now)}')

            with ui.row().classes('items-center gap-2'):
                ui.icon(_wifi_icon(item.rssi), color='grey-7').props('size=sm')
                ui.label(_rssi_text(item.rssi)).classes('text-grey-7')

            with ui.row().classes('items-center gap-2'):
                ui.icon(_battery_icon(item.battery_voltage), color=_battery_color(item.battery_voltage)).props('size=sm')
                ui.label(_battery_text(item.battery_voltage)).classes('text-grey-7')

            if item.device_url:
                ui.separator()
                ui.link('Open in nice4iot ↗', item.device_url, new_tab=True).classes('text-caption text-grey')

    _body(key)


# Combined active/provisioning/online state -> (icon, color, tooltip), mirroring
# nice4iot's own project Devices grid status dot (app/core/device/ui.py) for a
# consistent status vocabulary across both UIs. Inactive beats everything else,
# then pending provisioning approval, then plain online/offline.
_STATUS_ICONS: dict[str, tuple[str, str, str]] = {
    'online': ('circle', 'positive', 'Active, provisioned, online'),
    'offline': ('circle', 'orange', 'Active, provisioned, offline'),
    'pending': ('pending', 'purple', 'Active, pending provisioning approval'),
    'inactive': ('circle', 'grey-5', 'Inactive'),
}
_STATUS_LABELS = {'online': 'Online', 'offline': 'Offline',
                  'pending': 'Pending provisioning approval', 'inactive': 'Inactive'}


def _status_key(item: RoomDisplayRow) -> str:
    if not item.is_active:
        return 'inactive'
    if not item.is_provisioning_approved:
        return 'pending'
    return 'online' if item.online else 'offline'


def _status_icon(item: RoomDisplayRow) -> ui.icon:
    icon, color, tooltip = _STATUS_ICONS[_status_key(item)]
    return ui.icon(icon, color=color).tooltip(tooltip)


def _rssi_text(rssi: Optional[int]) -> str:
    return f'{rssi} dBm' if rssi is not None else 'No signal data yet'


def _battery_text(voltage: Optional[float]) -> str:
    return f'{voltage:.2f} V' if voltage is not None else 'No battery data yet'


# A previous version of this scaled through a 0-4 bar icon per name
# ('signal_wifi_{zero,four}_bar' for the endpoints, 'network_wifi_{one,two,
# three}_bar' for the middle three) on the theory that classic Material Icons
# (the font nicegui bundles) "oddly splits" wifi-bar icons across those two
# name prefixes. Rendering every candidate name against the actual bundled
# font (a temporary debug overlay injected into a live page, screenshotted)
# showed that theory was wrong on both counts: 'signal_wifi_zero_bar'/
# 'four_bar' don't exist as ligatures in the bundled font at all (empty,
# invisible), and the ones that did render ('network_wifi_one/two/three_bar')
# come from a visibly different glyph design than 'signal_wifi_off'/'wifi' --
# different internal bearings, so swapping between them shifted the visible
# icon left/right within its fixed-size box from row to row. Three states,
# not five, but all confirmed to render and to share consistent bearings.
def _wifi_icon(rssi: Optional[int]) -> str:
    """No-data / weak / good WiFi signal icon name."""
    if rssi is None:
        return 'signal_wifi_off'
    if rssi >= -70:
        return 'wifi'
    return 'signal_wifi_bad'


# Numeric 'battery_N_bar' names -- not the word-form ('battery_six_bar', ...)
# this used before, which doesn't exist as a ligature in the bundled font at
# all (see the _wifi_icon comment above for how that was verified).
_BATTERY_BARS = tuple(f'battery_{i}_bar' for i in range(7))
_BATTERY_EMPTY_V = 3.0   # single-cell Li-ion/LiPo cutoff -- adjust once real hardware data arrives
_BATTERY_FULL_V = 4.15


def _battery_icon(voltage: Optional[float]) -> str:
    """Battery voltage (V) -> a 0-6 bar icon, assuming a typical single-cell
    Li-ion/LiPo pack. battery_unknown with no reading at all (nice4iot
    doesn't expose this yet, see docs/nice4iot-extension-wishlist.md),
    battery_alert below the assumed empty cutoff, battery_full at/above the
    assumed full voltage."""
    if voltage is None:
        return 'battery_unknown'
    if voltage < _BATTERY_EMPTY_V:
        return 'battery_alert'
    if voltage >= _BATTERY_FULL_V:
        return 'battery_full'
    step = (_BATTERY_FULL_V - _BATTERY_EMPTY_V) / len(_BATTERY_BARS)
    index = min(len(_BATTERY_BARS) - 1, int((voltage - _BATTERY_EMPTY_V) / step))
    return _BATTERY_BARS[index]


def _battery_color(voltage: Optional[float]) -> str:
    return 'negative' if voltage is not None and voltage < _BATTERY_EMPTY_V else 'grey-7'
