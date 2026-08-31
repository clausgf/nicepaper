from nicegui import ui
from niceview import Field, ModelForm

from extensions.epaper.paths import EpaperPaths
from extensions.epaper.project_config.backend import get_project_config, save_project_config
from extensions.epaper.ui.forms import COL, FORM_STYLE, ROW, hints

_LOCATION_HINT = 'Used by weather widgets that set no location of their own'

_LAYOUT = [
    ['## Weather', COL, [ROW, 'latitude', 'longitude']],
    ['## Home Assistant', COL, 'homeassistant_url', 'homeassistant_token'],
]

_FIELD_INFOS = {
    # explicit labels: the humanized field names would all read "Homeassistant
    # ..." (one word, wrong spelling) and repeat the section heading
    'homeassistant_url': Field(label='Home Assistant URL'),
    # the token is a secret: masked in the field, still stored as plain text
    # in the config file (see ProjectConfig / SECURITY.md)
    'homeassistant_token': Field(label='Long-lived access token', props='type=password'),
    **hints(latitude=_LOCATION_HINT, longitude=_LOCATION_HINT),
}


def project_config_fields(paths: EpaperPaths) -> None:
    """
    The ProjectConfig editing fields, no ui.card()/ui.expansion() of their
    own, matching global_config_fields()'s contract. Unlike GlobalConfig,
    ProjectConfig's storage location is fully determined by `paths` -- so
    this loads, edits and persists it end to end, with no external persist
    callback needed.
    """
    config = get_project_config(paths)
    ModelForm.from_item(config, layout=_LAYOUT, field_infos=_FIELD_INFOS,
                        on_change=lambda e: save_project_config(paths, config), **FORM_STYLE).render()


def project_config_card(paths: EpaperPaths) -> None:
    """Card wrapper around project_config_fields(), used both by the
    standalone Settings page and nice4iot's 'Settings' project tab --
    register_project_tab (unlike register_global_card) supplies no card
    chrome of its own, so every project tab owns its own ui.card()."""
    with ui.card().classes('w-full'):
        ui.label('E-Paper Project Settings').classes('text-subtitle1')
        project_config_fields(paths)
