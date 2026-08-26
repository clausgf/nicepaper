"""
Displays: the simplified UI's flat, project-wide list of e-paper displays,
so nice4iot devices can be assigned a screen without opening nice4iot's own
device UI -- meant for people who shouldn't need to. A display is a nice4iot
device (see extensions/epaper/__init__.py, register_device_card).

`render_displays()` builds a niceview DrillDownWrapper over
`RoomDisplaysAdapter(paths, project_name)` (no room_id -- every device in the
project, bound to a room or not): list, Add and Delete are all disabled here
(a display is a nice4iot device we neither create nor unbind from this
project-wide view; room assignment happens in the room's own Displays tab,
room/simplified_ui.py, which has its own drill-down list instead of this
one). Only Screen is editable; everything else is read-only, hand-rendered
rather than through ModelForm/ModelList, so it can show icons (status, RSSI,
battery) instead of plain field values.
"""
import datetime
from typing import Optional

import niceview
from nicegui import ui
from niceview import CollectionAdapter, DrillDownWrapper, ModelForm

from extensions.epaper.display.backend import RoomDisplaysAdapter, available_screen_ids
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
    in both list and detail already, so it isn't repeated here."""
    item = adapter.read(key)
    # filtered to the device's own panel type if it has one set (devicebinding/ui.py)
    screen_ids = available_screen_ids(paths, item.device_name)

    with ui.column().classes('w-full gap-3'):
        with ui.row().classes('items-center gap-1 text-grey-7'):
            ui.icon('meeting_room').props('size=xs')
            if item.room_label:
                ui.label(f'{item.room_label} — {item.building or "—"} / {item.floor or "—"} / {item.room_number}')
            else:
                ui.label('Not assigned to a room')

        # an empty options list crashes the select widget, so fall back to a
        # plain hinted field rather than passing one.
        screen_field = (niceview.Field(widget_type='ui.select', options=screen_ids, clearable=True)
                       if screen_ids else niceview.Field(hint='No screens yet — add one in Templates'))
        ModelForm.from_adapter(RoomDisplayRow, adapter, key, autosave=True,
                               include=['screen_id'],
                               field_infos={'screen_id': screen_field},
                               ).render()

        render_device_preview(paths, item.device_name, item.screen_id, image_base_url)

        with ui.row().classes('items-center gap-2'):
            _status_icon(item).props('size=sm')
            now = datetime.datetime.now(datetime.timezone.utc)
            ui.label(f'{"Online" if item.online else "Offline"} · last seen {humanize_age(item.last_seen_at, now)}')

        with ui.row().classes('items-center gap-2'):
            ui.icon(_wifi_icon(item.rssi), color='grey-7').props('size=sm')
            ui.label(_rssi_text(item.rssi)).classes('text-grey-7')

        with ui.row().classes('items-center gap-2'):
            ui.icon(_battery_icon(item.battery_voltage), color=_battery_color(item.battery_voltage)).props('size=sm')
            ui.label(_battery_text(item.battery_voltage)).classes('text-grey-7')

        if item.device_url:
            ui.separator()
            ui.link('Open in nice4iot ↗', item.device_url, new_tab=True).classes('text-caption text-grey')


def _status_icon(item: RoomDisplayRow) -> ui.icon:
    return ui.icon('circle', color='positive' if item.online else 'grey-5') \
        .tooltip('Online' if item.online else 'Offline')


def _rssi_text(rssi: Optional[int]) -> str:
    return f'{rssi} dBm' if rssi is not None else 'No signal data yet'


def _battery_text(voltage: Optional[float]) -> str:
    return f'{voltage:.2f} V' if voltage is not None else 'No battery data yet'


# RSSI (dBm) -> a 0-4 bar icon. Classic Material Icons (the font nicegui
# bundles) oddly splits these five icons across two name prefixes --
# signal_wifi_{zero,four}_bar for the endpoints, network_wifi_{one,two,
# three}_bar for the middle three -- verified against the actual bundled
# font (nicegui/static/fonts.css), not guessed from the newer Material
# Symbols naming, which uses different names.
def _wifi_icon(rssi: Optional[int]) -> str:
    """Typical WiFi signal bands in dBm (excellent/good/fair/weak/very weak).
    signal_wifi_off when there's no reading at all (nice4iot doesn't expose
    RSSI yet, see docs/nice4iot-extension-wishlist.md)."""
    if rssi is None:
        return 'signal_wifi_off'
    if rssi >= -60:
        return 'signal_wifi_four_bar'
    if rssi >= -70:
        return 'network_wifi_three_bar'
    if rssi >= -80:
        return 'network_wifi_two_bar'
    if rssi >= -90:
        return 'network_wifi_one_bar'
    return 'signal_wifi_zero_bar'


_BATTERY_BARS = ('battery_zero_bar', 'battery_one_bar', 'battery_two_bar', 'battery_three_bar',
                 'battery_four_bar', 'battery_five_bar', 'battery_six_bar')
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
