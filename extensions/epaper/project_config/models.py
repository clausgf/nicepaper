from typing import Annotated

import niceview
from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    """
    Settings that differ between projects/roots -- as opposed to GlobalConfig,
    which is the same for every screen regardless of which project it belongs
    to. Persisted at EpaperPaths.project_config_file, one file per root.

    Home Assistant and the weather default location moved here from
    GlobalConfig: a project stands for one site (one building, one HA
    instance), and different projects on the same nice4iot install can be
    different sites.
    """
    latitude: Annotated[float,
                niceview.Field(hint="Default latitude for weather widgets that set no location of their own.")] = 52.52
    longitude: Annotated[float,
                niceview.Field(hint="Default longitude for weather widgets that set no location of their own.")] = 13.405

    homeassistant_url: Annotated[str,
                Field(title="Home Assistant URL"),
                niceview.Field(hint="Base URL of the Home Assistant instance, e.g. 'http://homeassistant.local:8123', without the '/api' suffix which is added automatically. Empty disables the HomeAssistant widget.")] = ""
    homeassistant_token: Annotated[str,
                Field(title="Long-lived access token"),
                niceview.Field(hint="Long-lived access token, created on the Home Assistant profile page. Stored in plain text in this config file, like every other field -- see SECURITY.md; give it a read-only user's token if that matters.")] = ""
