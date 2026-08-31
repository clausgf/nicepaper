"""
Everything the editor knows about a widget *type*, one entry per type.

This used to be spread over three parallel dicts (models, icons, titles)
and three if-chains (`_default_widget`, `_widget_label`, the per-type half
of the detail form) in screen/ui.py, all keyed by the same eight
strings -- so adding a widget type meant finding six places and matching
their order. Now it is one WIDGET_TYPES entry, next to the two other
places a type is declared: its model (screen/models.py) and its
drawing class (core/widgets/__init__.py's WIDGET_CLASSES).

A form is a niceview layout plus the field_infos that differ from the
defaults, so most entries are declarative. `content` and `field_infos`
may also be callables of (widget, paths) for the two types whose form
depends on the widget's own values (Image's url/file, Home Assistant's
gauge/value) or on the project directory (Image's file list); those name
the deciding field in `refresh_on` so changing it rebuilds the form.
`extra` renders what is not a field at all -- a button, a warning.
"""
from dataclasses import dataclass, field as dataclass_field
from typing import Any, Callable, List, Optional, Union

from nicegui import ui
from niceview import Field, ModelForm

from extensions.epaper.catalog.models import Palette
from extensions.epaper.config import resource_paths
from extensions.epaper.core.datasources.image import clear_cache as clear_image_cache
from extensions.epaper.global_config.backend import app_config
from extensions.epaper.project_config.backend import get_project_config
from extensions.epaper.screen.models import (
    DateWidgetModel, HomeAssistantWidgetModel, ImageWidgetModel, RoomCalendarWidgetModel,
    ScreenModel, TextWidgetModel, WeatherChartWidgetModel, WeatherForecastWidgetModel,
    WeatherNowWidgetModel, WeatherWidgetModel, WidgetModel,
)
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.compact_fields import compact_color_field, compact_font_field
from extensions.epaper.ui.forms import (
    ALIGNMENT_HINT, COL, DATE_PATTERN_HINT, FORM_STYLE, LOCATION_HINT, ROW, ROW_CENTER,
    SHORT_DATE_PATTERN_HINT, TIME_PATTERN_HINT, hints,
)

# image files selectable by the Image widget (Pillow-readable raster formats)
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')


@dataclass(frozen=True)
class WidgetType:
    """One widget type as the editor sees it."""
    model: type[WidgetModel]
    icon: str
    title: str
    summary: Callable[[Any, EpaperPaths], str]
    """One line identifying an instance in the widget list. Takes `paths`
    since a weather widget's summary reads the project's default location."""
    content: Union[list, Callable[[Any, EpaperPaths], list]]
    """The Content section as layout entries; the Layout and Appearance
    sections above it are the same for every type (see _layout())."""
    defaults: dict = dataclass_field(default_factory=dict)
    """Values for the required fields of a newly added widget. They are
    deliberately non-empty: niceview enforces required fields at the widget
    level and commits an item only once it validates as a whole, so a
    widget created with empty required strings would block every other
    edit in its form until they are filled in."""
    field_infos: Union[dict, Callable[[Any, EpaperPaths], dict]] = dataclass_field(default_factory=dict)
    extra: Optional[Callable[[ModelForm, Any, EpaperPaths, Callable[[], None]], None]] = None
    """Rendered below the form, for what is not a field: a button, a warning."""
    refresh_on: tuple[str, ...] = ()
    """Fields whose change rebuilds the form, because `content` reads them."""
    font: bool = True
    """Whether the Appearance section offers font_name/font_size."""
    colors: bool = True
    """Whether the Appearance section offers color_primary/color_accent."""


def _resolve(value: Any, widget: WidgetModel, paths: EpaperPaths) -> Any:
    return value(widget, paths) if callable(value) else value


# --- summaries for the widget list ------------------------------------------

def _location_summary(widget: WeatherWidgetModel, paths: EpaperPaths) -> str:
    """A weather widget's location: its own coordinates, or a note that it
    follows the project default -- which is the one thing a bare
    '52.52, 13.41' could not tell apart."""
    project_config = get_project_config(paths)
    location = widget.resolved_location(project_config.latitude, project_config.longitude)
    if location is None:
        return '(no location)'
    text = f'{location[0]:.2f}, {location[1]:.2f}'
    return text if (widget.latitude or widget.longitude) else f'{text} (default)'


def _chart_summary(widget: WeatherChartWidgetModel, paths: EpaperPaths) -> str:
    metrics = ' + '.join(m for m in (widget.primary_metric, widget.secondary_metric) if m)
    location = _location_summary(widget, paths)
    return f'{location} · {metrics}' if metrics else f'{location} (no metric)'


def _homeassistant_summary(widget: HomeAssistantWidgetModel, paths: EpaperPaths) -> str:
    entity = widget.entity_id or '(no entity)'
    return f'{entity}{f".{widget.attribute}" if widget.attribute else ""} · {widget.display}'


# --- the two types whose form is not a fixed list of fields -----------------

def _image_files(paths: EpaperPaths) -> list[str]:
    """Image file names available in the project directory."""
    return sorted(p.name for p in paths.asset_dir.glob('*')
                  if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _image_field_infos(widget: ImageWidgetModel, paths: EpaperPaths) -> dict:
    # keep a now-missing file selectable/visible, like a dangling schedule
    files = _image_files(paths)
    options = files + ([widget.file] if widget.file and widget.file not in files else [])
    # a select needs something to select: niceview rejects an empty options
    # list outright (ValueError, i.e. no form at all), and a project simply
    # has no image files until someone adds one
    file_field = (Field(widget_type='ui.select', options=options, clearable=True) if options
                  else Field(hint='No image files in the project directory yet'))
    return {
        # no hand-written caption next to the toggle: niceview renders the
        # field's own label above widgets that have no label slot
        'source_type': Field(widget_type='ui.toggle'),
        'file': file_field,
        'reload_each_time': Field(label='Reload on every rendering'),
    }


def _image_extra(form: ModelForm, widget: ImageWidgetModel, paths: EpaperPaths,
                 persist: Callable[[], None]) -> None:
    def reload_now() -> None:
        clear_image_cache(paths, widget)
        persist()  # rewrite the screen file -> re-render picks up the refetch
        ui.notify('Image reloaded', type='positive')

    ui.button('Reload now', icon='refresh', on_click=reload_now).props('dense flat')


def _homeassistant_extra(form: ModelForm, widget: HomeAssistantWidgetModel, paths: EpaperPaths,
                         persist: Callable[[], None]) -> None:
    if not get_project_config(paths).homeassistant_url:
        ui.label('No Home Assistant URL configured — set it in the project settings.'
                 ).classes('text-caption text-negative')


WIDGET_TYPES: dict[str, WidgetType] = {
    'Text': WidgetType(
        model=TextWidgetModel, icon='text_fields', title='Text Widget',
        summary=lambda w, paths: w.text or '(empty text)',
        defaults={'text': 'Text'},
        content=['text', 'alignment'],
    ),
    'Date': WidgetType(
        model=DateWidgetModel, icon='event', title='Date Widget',
        summary=lambda w, paths: w.date_format or 'Date',
        content=['date_format', 'alignment'],
        field_infos=hints(date_format=DATE_PATTERN_HINT),
    ),
    'RoomCalendar': WidgetType(
        model=RoomCalendarWidgetModel, icon='calendar_month', title='Room Calendar Widget',
        summary=lambda w, paths: '(room calendar — shows the rendering device\'s own room)',
        defaults={},
        content=[[ROW, 'date_format_long', 'date_format', 'time_format']],
        field_infos=hints(date_format_long=DATE_PATTERN_HINT,
                          date_format=SHORT_DATE_PATTERN_HINT,
                          time_format=TIME_PATTERN_HINT),
    ),
    'WeatherNow': WidgetType(
        model=WeatherNowWidgetModel, icon='wb_sunny', title='Weather (Now) Widget',
        summary=_location_summary,
        content=[[ROW, 'latitude', 'longitude']],
    ),
    'WeatherForecast': WidgetType(
        model=WeatherForecastWidgetModel, icon='view_column', title='Weather (Forecast) Widget',
        summary=_location_summary,
        content=[[ROW, 'latitude', 'longitude'], 'forecast_hours'],
    ),
    'WeatherChart': WidgetType(
        model=WeatherChartWidgetModel, icon='show_chart', title='Weather (Chart) Widget',
        summary=_chart_summary,
        content=[[ROW, 'latitude', 'longitude'],
                 [ROW, 'primary_metric', 'secondary_metric'], [ROW, 'forecast_hours', 'line_style']],
        field_infos={'line_style': Field(widget_type='ui.select', options=['solid', 'dashed', 'dotted']),
                    # clearable: either metric can be emptied to drop its trace
                    # (see WeatherChartWidgetModel), not just left at the default
                    'primary_metric': Field(clearable=True), 'secondary_metric': Field(clearable=True)},
    ),
    'Image': WidgetType(
        model=ImageWidgetModel, icon='image', title='Image Widget',
        summary=lambda w, paths: (w.url if w.source_type == 'url' else w.file) or '(no image)',
        # only the source that is actually in use, so the other one can't be
        # filled in and silently ignored
        content=lambda w, paths: ['source_type', 'file' if w.source_type == 'file' else 'url',
                                  'reload_each_time'],
        field_infos=_image_field_infos,
        extra=_image_extra,
        refresh_on=('source_type',),
        font=False,  # the Image widget has no text or lines of its own
        colors=False,
    ),
    'HomeAssistant': WidgetType(
        model=HomeAssistantWidgetModel, icon='sensors', title='Home Assistant Widget',
        summary=_homeassistant_summary,
        defaults={'entity_id': 'sensor.example'},
        # only the fields that matter for the chosen display (gauge scale
        # vs. text alignment)
        content=lambda w, paths: [
            'entity_id', [ROW, 'attribute', 'label', 'unit'],
            [ROW_CENTER, 'decimals', 'display', 'show_label'],
            *([[ROW_CENTER, 'gauge_style', 'min_value', 'max_value']]
              if w.display == 'gauge' else ['alignment']),
        ],
        field_infos={'display': Field(widget_type='ui.toggle'),
                     'gauge_style': Field(widget_type='ui.toggle'),
                     'decimals': Field(classes='w-32')},
        extra=_homeassistant_extra,
        refresh_on=('display',),
    ),
}


def new_widget(widget_type: str) -> WidgetModel:
    """A new widget of the given type, its required fields pre-filled (see
    WidgetType.defaults). Every widget starts at the top left corner; the
    weather widgets deliberately start without coordinates so a new one
    follows the default location from the global settings rather than the
    0/0 in the Atlantic."""
    entry = WIDGET_TYPES[widget_type]
    return entry.model(position_x=0, position_y=0, **entry.defaults)


def _layout_top(entry: WidgetType) -> list:
    """Layout + Appearance sections shared by every widget -- position/size
    and background/clipping. font_name/font_size and color_primary/
    color_accent render as compact controls instead (see
    _render_appearance_extras()), between this and _layout_content()."""
    return [
        ['## Layout', COL, [ROW, 'position_x', 'position_y'], [ROW, 'size_width', 'size_height']],
        ['## Appearance', COL, [ROW, 'init_background', 'clipping']],
    ]


def _layout_content(entry: WidgetType, widget: WidgetModel, paths: EpaperPaths) -> list:
    return [['## Content', COL, *_resolve(entry.content, widget, paths)]]


def _font_names() -> List[str]:
    return sorted(p.name for p in resource_paths.font_path.glob('*') if p.is_file())


def _field_infos(entry: WidgetType, widget: WidgetModel, paths: EpaperPaths) -> dict:
    """The shared field customizations, with the type's own merged on top."""
    shared = {
        'alignment': Field(hint=ALIGNMENT_HINT, classes='w-40'),
        'latitude': Field(hint=LOCATION_HINT, clearable=True),
        'longitude': Field(hint=LOCATION_HINT, clearable=True),
    }
    return {**shared, **_resolve(entry.field_infos, widget, paths)}


def _render_appearance_extras(adapter, key: str, entry: WidgetType,
                              screen: Optional[ScreenModel], palette: Optional[Palette]) -> None:
    """The compact font/color controls between the Layout+Appearance and
    Content sections -- see compact_fields.py for why these can't just be
    more ModelForm fields."""
    # the global accent is itself optional (clearable in the settings), same
    # fallback screen/backend.py's Screen.colors uses -- some concrete color
    # has to reach the swatch either way
    default_accent = app_config.color_accent or app_config.color_primary
    if screen is not None:
        _, screen_primary, screen_accent = screen.resolved_colors(
            app_config.color_background, app_config.color_primary, default_accent)
    else:
        screen_primary, screen_accent = app_config.color_primary, default_accent
    palette_hex = [f'#{r:02x}{g:02x}{b:02x}' for r, g, b in palette.palette] if palette else None
    font_options = _font_names()

    def save(**fields: Any) -> None:
        item = adapter.read(key)
        for name, value in fields.items():
            setattr(item, name, value)
        adapter.update(item)
        row.refresh()

    @ui.refreshable
    def row() -> None:
        item = adapter.read(key)
        with ui.row().classes('items-center gap-3 q-px-sm q-pb-sm'):
            if entry.font:
                resolved_name, resolved_size = item.resolved_font(app_config.font_name, app_config.font_size)
                compact_font_field(
                    resolved_name=resolved_name, resolved_size=resolved_size,
                    default_name=app_config.font_name, default_size=app_config.font_size,
                    font_name=item.font_name, font_size=item.font_size, font_options=font_options,
                    on_save=lambda name, size: save(font_name=name, font_size=size))
            if entry.colors:
                resolved_primary, resolved_accent = item.resolved_colors(screen_primary, screen_accent)
                compact_color_field(
                    label='Primary color', value=item.color_primary, resolved=resolved_primary,
                    default=screen_primary, palette_hex=palette_hex,
                    on_change=lambda c: save(color_primary=c))
                compact_color_field(
                    label='Accent color', value=item.color_accent, resolved=resolved_accent,
                    default=screen_accent, palette_hex=palette_hex,
                    on_change=lambda c: save(color_accent=c))

    row()


def render_widget_form(widget: WidgetModel, adapter, key: str, paths: EpaperPaths,
                       persist: Callable[[], None], refresh: Callable[[], None],
                       screen: Optional[ScreenModel] = None, palette: Optional[Palette] = None) -> None:
    """The editing form for one widget, autosaving through `adapter`.

    `refresh` rebuilds the detail view; it is called when a field in the
    type's `refresh_on` changes, since those decide which fields the form
    shows at all. `screen`/`palette` (the screen being edited and its
    resolved Palette, see catalog/backend.py::get_palette) inform the
    compact color field's defaults/options -- both optional so this can
    still be called without a screen in scope (falls back to the global
    defaults and an unrestricted color picker)."""
    entry = WIDGET_TYPES[widget.widget_type]

    def on_change(e) -> None:
        if e.field_name in entry.refresh_on:
            refresh()

    top_form = ModelForm.from_adapter(
        entry.model, adapter, key, autosave=True, on_change=on_change,
        layout=_layout_top(entry),
        field_infos=_field_infos(entry, widget, paths), **FORM_STYLE)
    top_form.render()

    if entry.font or entry.colors:
        _render_appearance_extras(adapter, key, entry, screen, palette)

    content_form = ModelForm.from_adapter(
        entry.model, adapter, key, autosave=True, on_change=on_change,
        layout=_layout_content(entry, widget, paths),
        field_infos=_field_infos(entry, widget, paths), **FORM_STYLE)
    content_form.render()
    if entry.extra is not None:
        entry.extra(content_form, widget, paths, persist)
