import importlib.resources
from typing import List, Optional, Tuple
from pydantic import BaseModel, DirectoryPath, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resource_dir(name: str) -> str:
    # bundled inside the extensions.epaper package (see pyproject.toml package-data),
    # so this resolves correctly whether epaper-nice runs standalone (cwd = repo root)
    # or is installed as a dependency inside another process (e.g. nice4iot)
    return str(importlib.resources.files(__package__) / "resources" / name)


class ColorModel(BaseModel):
    """
    Color model for the e-paper display.
    """
    id: str
    name: str
    palette: List[Tuple[int, int, int]]
    background_color_index: int = 1


class Config(BaseSettings):
    """
    Application settings that are the same for every screen regardless of
    which project/root it belongs to. File locations (screens, schedules,
    images, ...) are per-root and computed via paths.EpaperPaths instead.
    """
    # secret for NiceGUI browser session storage; override via the
    # STORAGE_SECRET environment variable in production
    storage_secret: str = "geheim"

    font_path: DirectoryPath = Field(default_factory=lambda: _resource_dir("fonts"))
    icon_path: DirectoryPath = Field(default_factory=lambda: _resource_dir("icons"))

    ical_update_interval_s: int = 600
    ical_max_days: int = 30

    no_appointments: str = "Keine Termine"
    next_appointment: str = "Nächster Termin"
    current_appointment: str = "Aktueller Termin"
    further_appointments: str = "Weitere Termine"
    roomcalendar_date_format_long: str = "EEEE, dd.MM.yyyy"
    roomcalendar_date_format_short: str = "dd.MM.yy"
    roomcalendar_time_format: str = "HH:mm"

    locale: str = 'de_DE.utf8'
    timezone: str = 'Europe/Berlin'
    date_format: str = 'dd.MM.yy'
    time_format: str = 'HH:mm'
    font: Tuple[str, int] = ("Ubuntu-Regular.ttf", 16)
    color_background: Optional[Tuple[int, int, int]] = (255, 255, 255)
    color_primary: Optional[Tuple[int, int, int]] = (0, 0, 0)

    epaper_color_models: List[ColorModel] = [
        ColorModel(id='bw', name='Black on white', palette=[(0,0,0), (255,255,255)]),
        ColorModel(id='bwr', name='Black/Red on white', palette=[(0,0,0), (255,255,255), (255,0,0)]),
        ColorModel(id='gs4', name='4-Greyscale on white', palette=[(0,0,0), (255,255,255), (128,128,128), (192,192,192)]),
        ColorModel(id='c7', name='7-color C7', palette=[(0,0,0), (255,255,255), (0,255,0), (0,0,255), (255,0,0), (255,255,0), (255,165,0)]),
        ColorModel(id='e6', name='Spectra E6', palette=[(0,0,0), (255,255,255), (255,255,0), (255,0,0), (0,0,255), (0,255,0)]),
    ]


app_config = Config()
