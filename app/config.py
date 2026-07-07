from typing import List, Literal, Optional, Tuple
from pydantic import BaseModel, DirectoryPath
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    Application settings.
    """
    # basic app settings
    # secret for NiceGUI browser session storage; override via the
    # STORAGE_SECRET environment variable in production
    storage_secret: str = "geheim"

    font_path: DirectoryPath = "resources/fonts"
    icon_path: DirectoryPath = "resources/icons"

    image_dir: DirectoryPath = "data/images"
    screen_dir: DirectoryPath = "data/screens"
    schedule_dir: DirectoryPath = "data/schedules"
    ical_dir: DirectoryPath = "data/ical"
    ical_update_interval_s: int = 600
    ical_max_days: int = 30
    organizer_names_file: Optional[str] = "data/organizer_names.json"

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

    # epaper_display_types: List[EpaperDisplayType] = [
    #     EpaperDisplayType(id='gdew042t2', name='Good Display GDEW042T2/Waveshare 4.2" 4 Grayscale', size=(400, 300), palette=[(255, 255, 255), (0, 0, 0)]),
    #     EpaperDisplayType(id='gdeh075z90', name='Good Display GDEW075Z90/Waveshare 7.5" BWR', size=(880, 528), palette=[(255, 255, 255), (0, 0, 0), (255, 0, 0)]),
    #     #EpaperDisplayType(id='epd_7.5', name='7.5 inch', size=(640, 384), palette=[(255, 255, 255), (0, 0, 0)]),
    #     #EpaperDisplayType(id='epd_7.5c', name='7.5 inch color', size=(640, 384), palette=[(255, 255, 255), (0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255)]),
    # ]
    epaper_color_models: List[ColorModel] = [
        ColorModel(id='bw', name='Black on white', palette=[(0,0,0), (255,255,255)]),
        ColorModel(id='bwr', name='Black/Red on white', palette=[(0,0,0), (255,255,255), (255,0,0)]),
        ColorModel(id='gs4', name='4-Greyscale on white', palette=[(0,0,0), (255,255,255), (128,128,128), (192,192,192)]),
        ColorModel(id='c7', name='7-color C7', palette=[(0,0,0), (255,255,255), (0,255,0), (0,0,255), (255,0,0), (255,255,0), (255,165,0)]),
        ColorModel(id='e6', name='Spectra E6', palette=[(0,0,0), (255,255,255), (255,255,0), (255,0,0), (0,0,255), (0,255,0)]),
    ]


app_config = Config()
