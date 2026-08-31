"""
Everything the editor knows about a widget *type*, one WIDGET_TYPES entry
per type -- next to its model (screen/models.py) and drawing class
(core/widgets/__init__.py's WIDGET_CLASSES).

A form is a niceview layout over the model's own fields; static per-field
UI lives on the model (Annotated niceview.Field), not here. `content`,
`field_infos` and `colors` may be callables of (widget, paths) for parts
that depend on the widget's own value or the project's files; name the
deciding field in `refresh_on` to rebuild the form on change. `extra`
renders what isn't a field: a button, a warning.
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
    BoxWidgetModel, DateWidgetModel, HomeAssistantWidgetModel, ImageWidgetModel, LineWidgetModel,
    RoomCalendarWidgetModel, TextWidgetModel, WeatherChartWidgetModel, WeatherForecastWidgetModel,
    WeatherNowWidgetModel, WeatherWidgetModel, WidgetModel,
)
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.compact_fields import compact_color_field, compact_font_field

# image files selectable by the Image widget (Pillow-readable raster formats)
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')

# Every widget has these two; types with more colors extend this dict.
_DEFAULT_COLORS: dict[str, str] = {'color_primary': 'Primary color', 'color_background': 'Background color'}


@dataclass(frozen=True)
class WidgetType:
    """One widget type as the editor sees it."""
    model: type[WidgetModel]
    icon: str
    title: str
    summary: Callable[[Any, EpaperPaths], str]
    """One line identifying an instance in the widget list."""
    content: Union[list, Callable[[Any, EpaperPaths], list]]
    """The Content section as layout entries; Layout/Appearance are shared."""
    field_infos: Union[dict, Callable[[Any, EpaperPaths], dict]] = dataclass_field(default_factory=dict)
    """Field customization for what can't live on the model -- only Image's
    'file' select needs this (options depend on the project directory)."""
    extra: Optional[Callable[[ModelForm, Any, EpaperPaths, Callable[[], None]], None]] = None
    """Rendered below the form, for what is not a field: a button, a warning."""
    refresh_on: tuple[str, ...] = ()
    """Fields whose change rebuilds the form, because `content` reads them."""
    font: bool = True
    """Whether the Appearance section offers font_name/font_size."""
    colors: Union[dict[str, str], Callable[[Any, EpaperPaths], dict[str, str]]] = dataclass_field(
        default_factory=lambda: dict(_DEFAULT_COLORS))
    """Compact color swatches in the Appearance row: field name -> label."""


def _resolve(value: Any, widget: WidgetModel, paths: EpaperPaths) -> Any:
    return value(widget, paths) if callable(value) else value


# --- summaries for the widget list ------------------------------------------

def _box_summary(widget: BoxWidgetModel, paths: EpaperPaths) -> str:
    parts = [f'{widget.line_width}px border'] if widget.line_width > 0 else []
    if widget.init_background:
        parts.append('filled')
    if widget.corner_radius:
        parts.append(f'r={widget.corner_radius}')
    return ' · '.join(parts) if parts else '(invisible)'


def _line_summary(widget: LineWidgetModel, paths: EpaperPaths) -> str:
    return f'{widget.line_style} · {widget.line_width}px'


def _location_summary(widget: WeatherWidgetModel, paths: EpaperPaths) -> str:
    """Coordinates, or a note that it follows the project default."""
    project_config = get_project_config(paths)
    location = widget.resolved_location(project_config.latitude, project_config.longitude)
    if location is None:
        return '(no location)'
    text = f'lat,lon={location[0]:.2f},{location[1]:.2f}'
    return text if (widget.latitude or widget.longitude) else f'{text} (default)'


def _forecast_summary(widget: WeatherForecastWidgetModel, paths: EpaperPaths) -> str:
    return f'{_location_summary(widget, paths)} · hours={widget.forecast_hours}'


def _chart_summary(widget: WeatherChartWidgetModel, paths: EpaperPaths) -> str:
    metrics = ' + '.join(m for m in (widget.primary_metric, widget.secondary_metric) if m) or '(no metric)'
    return f'{_location_summary(widget, paths)} · hours={widget.forecast_hours} · {metrics}'


def _homeassistant_summary(widget: HomeAssistantWidgetModel, paths: EpaperPaths) -> str:
    entity = widget.entity_id or '(no entity)'
    # widget.label is only a manual override -- an unset one still shows a
    # label at render time (the entity's own friendly name), so it isn't
    # "(no label)"; only show_label=False actually draws no label at all
    label = '(no label)' if not widget.show_label else widget.label or '(entity name)'
    return f'{entity}{f".{widget.attribute}" if widget.attribute else ""} · {label} as {widget.display}'


# --- the two types whose form is not a fixed list of fields -----------------

def _image_files(paths: EpaperPaths) -> list[str]:
    """Image file names available in the project directory."""
    return sorted(p.name for p in paths.asset_dir.glob('*')
                  if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _image_field_infos(widget: ImageWidgetModel, paths: EpaperPaths) -> dict:
    files = _image_files(paths)
    # keep a now-missing file selectable, like a dangling schedule
    options = files + ([widget.file] if widget.file and widget.file not in files else [])
    # an empty options list is a hard ValueError for niceview's select
    file_field = (Field(widget_type='ui.select', options=options, clearable=True) if options
                  else Field(hint='No image files in the project directory yet'))
    return {'file': file_field}


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


_HOMEASSISTANT_COLORS = {**_DEFAULT_COLORS, 'color_fill': 'Fill color'}


WIDGET_TYPES: dict[str, WidgetType] = {
    'Text': WidgetType(
        model=TextWidgetModel, icon='text_fields', title='Text Widget',
        summary=lambda w, paths: w.text or '(empty text)',
        content=[['text', 'alignment']],
    ),
    'Date': WidgetType(
        model=DateWidgetModel, icon='event', title='Date Widget',
        summary=lambda w, paths: w.date_format or 'Date',
        content=[['date_format', 'alignment']],
    ),
    'Box': WidgetType(
        model=BoxWidgetModel, icon='crop_square', title='Box Widget',
        summary=_box_summary,
        content=[['line_width', 'corner_radius']],
        font=False,  # the Box widget has no text of its own
        colors={'color_primary': 'Border color', 'color_background': 'Fill color'},
    ),
    'Line': WidgetType(
        model=LineWidgetModel, icon='horizontal_rule', title='Line Widget',
        summary=_line_summary,
        content=[['line_width', 'line_style']],
        font=False,  # the Line widget has no text of its own
        colors={'color_primary': 'Line color'},
    ),
    'RoomCalendar': WidgetType(
        model=RoomCalendarWidgetModel, icon='calendar_month', title='Room Calendar Widget',
        summary=lambda w, paths: '(room calendar — shows the rendering device\'s own room)',
        content=[['date_format_long', 'date_format', 'time_format']],
    ),
    'WeatherNow': WidgetType(
        model=WeatherNowWidgetModel, icon='wb_sunny', title='Weather (Now) Widget',
        summary=_location_summary,
        content=[['latitude', 'longitude']],
    ),
    'WeatherForecast': WidgetType(
        model=WeatherForecastWidgetModel, icon='view_column', title='Weather (Forecast) Widget',
        summary=_forecast_summary,
        content=[['latitude', 'longitude', 'forecast_hours']],
    ),
    'WeatherChart': WidgetType(
        model=WeatherChartWidgetModel, icon='show_chart', title='Weather (Chart) Widget',
        summary=_chart_summary,
        content=[['latitude', 'longitude', 'forecast_hours'],
                 ['primary_metric', 'line_style_primary', 'secondary_metric', 'line_style_secondary']],
        colors={**_DEFAULT_COLORS, 'color_primary_series': 'Primary series',
               'color_secondary_series': 'Secondary series'},
    ),
    'Image': WidgetType(
        model=ImageWidgetModel, icon='image', title='Image Widget',
        summary=lambda w, paths: (w.url if w.source_type == 'url' else w.file) or '(no image)',
        # only the source in use, so the other one can't be filled in and ignored
        content=lambda w, paths: [['source_type', 'file' if w.source_type == 'file' else 'url'],
                                  'reload_each_time'],
        field_infos=_image_field_infos,
        extra=_image_extra,
        refresh_on=('source_type',),
        font=False,  # the Image widget has no text or lines of its own
        colors={},
    ),
    'HomeAssistant': WidgetType(
        model=HomeAssistantWidgetModel, icon='sensors', title='Home Assistant Widget',
        summary=_homeassistant_summary,
        # min_value/max_value only mean anything once a gauge shape is picked
        content=lambda w, paths: [
            ['entity_id', 'attribute'], ['show_label:shrink', 'label', 'decimals', 'unit'],
            ['display', *(['min_value', 'max_value'] if w.display != 'value' else [])],
        ],
        extra=_homeassistant_extra,
        refresh_on=('display',),
        colors=_HOMEASSISTANT_COLORS,
    ),
}


def new_widget(widget_type: str) -> WidgetModel:
    """A new widget, starting at the top left corner."""
    model = WIDGET_TYPES[widget_type].model
    # mypy only sees the type[WidgetModel] declared on WidgetType.model, not
    # which concrete subclass -- every one of them defaults widget_type itself
    return model(position_x=0, position_y=0)  # type: ignore[call-arg]


def _position_summary(widget: WidgetModel) -> str:
    """'(x,y)', or '(x,y,w,h)' once a fixed size is set."""
    x, y = widget.position
    if widget.size:
        w, h = widget.size
        return f'({x},{y},{w},{h})'
    return f'({x},{y})'


def widget_summary(widget: WidgetModel, paths: EpaperPaths) -> str:
    """One line identifying a widget instance in the list: position/size
    first (the same for every type), then WidgetType.summary's own detail."""
    entry = WIDGET_TYPES[widget.widget_type]
    return f'{_position_summary(widget)} · {entry.summary(widget, paths)}'


def _layout_top(entry: WidgetType) -> list:
    """Layout + Appearance sections shared by every widget type."""
    return [
        ['## Layout', ['position_x', 'position_y', 'size_width', 'size_height']],
        # ROW_CENTER: font/color controls join this row later, at a different height
        ['## Appearance', ['init_background:shrink', 'clipping']],
    ]


def _layout_content(entry: WidgetType, widget: WidgetModel, paths: EpaperPaths) -> list:
    return [['## Content', *_resolve(entry.content, widget, paths)]]


def _font_names() -> List[str]:
    return sorted(p.name for p in resource_paths.font_path.glob('*') if p.is_file())


def _render_appearance_extras(adapter, key: str, entry: WidgetType, colors: dict,
                              palette: Optional[Palette]) -> ui.element:
    """Compact font/color controls, moved to the front of the Appearance
    row by render_widget_form -- see compact_fields.py for why these
    aren't plain ModelForm fields. Returns the wrapper so the caller can
    reposition it; a plain ui.row() (not the refreshable itself) so that
    handle stays valid across refreshes."""
    palette_hex = [f'#{r:02x}{g:02x}{b:02x}' for r, g, b in palette.palette] if palette else None
    font_options = _font_names()

    def save(**fields: Any) -> None:
        item = adapter.read(key)
        for name, value in fields.items():
            setattr(item, name, value)
        adapter.update(item)
        controls.refresh()

    @ui.refreshable
    def controls() -> None:
        item = adapter.read(key)
        if entry.font:
            resolved_name, resolved_size = item.resolved_font(app_config.font_name, app_config.font_size)
            compact_font_field(
                resolved_name=resolved_name, resolved_size=resolved_size,
                default_name=app_config.font_name, default_size=app_config.font_size,
                font_name=item.font_name, font_size=item.font_size, font_options=font_options,
                on_save=lambda name, size: save(font_name=name, font_size=size))
        for field_name, label in colors.items():
            def on_color_change(c: str, field_name: str = field_name) -> None:
                save(**{field_name: c})
            compact_color_field(
                label=label, value=getattr(item, field_name), palette_hex=palette_hex,
                on_change=on_color_change)

    with ui.row().classes('items-center gap-3') as wrapper:
        controls()
    return wrapper


def render_widget_form(widget: WidgetModel, adapter, key: str, paths: EpaperPaths,
                       persist: Callable[[], None], refresh: Callable[[], None],
                       palette: Optional[Palette] = None) -> None:
    """The editing form for one widget, autosaving through `adapter`.
    `refresh` rebuilds the detail view when a `refresh_on` field changes.
    `palette` restricts the compact color swatches to it; omit for an
    unrestricted color picker."""
    entry = WIDGET_TYPES[widget.widget_type]

    def on_change(e) -> None:
        if e.field_name in entry.refresh_on:
            refresh()

    field_infos = _resolve(entry.field_infos, widget, paths)
    colors = _resolve(entry.colors, widget, paths)

    top_form = ModelForm.from_adapter(
        entry.model, adapter, key, autosave=True, on_change=on_change,
        layout=_layout_top(entry),
        field_infos=field_infos)
    top_form.render()

    if entry.font or colors:
        # reopen the toggles' row so font/colors land on the same line,
        # then move them in front of the toggles
        appearance_row = top_form.w('clipping', ui.switch).parent_slot
        assert appearance_row is not None  # just rendered above
        with appearance_row.parent:
            extras = _render_appearance_extras(adapter, key, entry, colors, palette)
        extras.move(target_index=0)

    content_form = ModelForm.from_adapter(
        entry.model, adapter, key, autosave=True, on_change=on_change,
        layout=_layout_content(entry, widget, paths),
        field_infos=field_infos)
    content_form.render()
    if entry.extra is not None:
        entry.extra(content_form, widget, paths, persist)
