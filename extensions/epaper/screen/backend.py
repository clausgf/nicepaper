import asyncio
import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image
from typing import Optional
import aiofiles

from extensions.epaper.catalog.backend import get_palette, get_panel_type, get_panel_types
from extensions.epaper.util import logger
from extensions.epaper.core import widgets
from extensions.epaper.devicebinding.backend import resolve_screen_and_room
from extensions.epaper.core.drawingcontext import DrawingContext
from extensions.epaper.core.imagecache import ImageCache, quantize
from extensions.epaper.global_config.backend import app_config
from extensions.epaper.catalog.models import Palette, PanelTypeModel
from extensions.epaper.room.backend import read_room
from extensions.epaper.room.models import RoomModel
from extensions.epaper.schedule.backend import UpdateSchedule, get_schedule_by_id
from extensions.epaper.screen.models import ImageMetadata, RoomCalendarWidgetModel, ScreenModel
from extensions.epaper.paths import EpaperPaths


def panel_label(config: ScreenModel, paths: EpaperPaths) -> str:
    """Compact human label for a screen's panel: the applied panel type's
    own name + GxEPD2 class when panel_type_id is set and still resolves in
    the catalog; otherwise (no preset, or a dangling id) a plain summary of
    the screen's own size and palette -- the screen itself carries no
    GxEPD2 class, only a panel-type preset does, so the fallback has none
    either. The editor is responsible for clearing panel_type_id once the
    screen's fields no longer match the preset it names (see screen/ui.py's
    on_field_change), so a resolved panel type here can be trusted to
    describe this screen.

    A free function (not just Screen.panel_label, which wraps this) so a
    screen listing (Templates) can use it from a plain ScreenModel without
    building a full, async-constructed Screen instance just for a label."""
    panel_type = get_panel_type(config.panel_type_id, paths)
    if panel_type is not None:
        return f'{panel_type.name} {panel_type.panel_id or ""}'.strip()
    parts = [f'{config.width}x{config.height}']
    if config.palette_id:
        palette = get_palette(config.palette_id, paths)
        parts.append(f'{config.palette_id} {len(palette.palette)}-color'
                    if palette is not None else config.palette_id)
    return ' '.join(parts)


class Screen:
    """
    A screen renders a collection of widgets with a specific layout
    on a canvas with a specific size in RGB format.

    Each widget is drawn in a data context, which consists of a
    static component and a dynamic component from data source instances.
    Data context is managed on a global,
    per-screen and per-widget basis. Widget level data context
    overwrites screen level context, which in turn overwrites
    global data context.
    """

    def __init__(self, id: str, config: ScreenModel, config_mtime: datetime.datetime,
                 paths: EpaperPaths, update_schedule: Optional[UpdateSchedule] = None,
                 room: Optional[RoomModel] = None):
        self.id = id
        self.config = config
        self.config_mtime = config_mtime
        self.paths = paths
        self.widgets = []
        self.update_schedule = update_schedule
        # the room the requesting device is bound to (RoomCalendarWidget) --
        # None for a screen with no room-aware widget, or previewed/rendered
        # without device context (e.g. the editor, or a bare screen id).
        # Kept mutable (see get_screen_by_id()'s cache-hit path) so a cached
        # Screen instance always renders with the current room, not whatever
        # room first populated the cache entry.
        self.room = room
        # two devices sharing one screen (a synthetic RoomCalendar template)
        # must not share a cached image -- fold the room into the cache's
        # own directory name, but only when there is one, so every screen
        # that isn't room-aware keeps today's cache path unchanged
        cache_name = f"{self.id}__{room.id}" if room is not None else self.id
        self.image_cache = ImageCache(paths.image_dir, cache_name)

        logger.info(f"Creating screen id={self.id}")
        for widget_id, widget_config in enumerate(self.config.widgets):
            logger.debug(f"creating widget from {widget_config}")
            widget_class = widgets.WIDGET_CLASSES.get(widget_config.widget_type)
            if widget_class is None:
                logger.error(f"Error creating widget: no drawing class for {widget_config.widget_type!r}")
                continue
            self.widgets.append(widget_class(str(widget_id), widget_config))


    async def get_image_path(self, raw: bool = False) -> Optional[str]:
        """
        Path of the image to serve: quantized to this screen's palette,
        or the unquantized RGB render when the screen has no palette.
        `raw` forces the RGB render regardless -- the editor preview shows
        it next to the quantized image, so a color that dithers can be
        compared against what was actually drawn.
        """
        return await self.image_cache.get_image_path(None if raw else self.palette)


    async def get_image(self, raw: bool = False) -> Optional[Image.Image]:
        """
        The image to serve, see get_image_path().
        """
        return await self.image_cache.get_image(None if raw else self.palette)


    async def get_metadata(self) -> Optional[ImageMetadata]:
        """
        Get the metadata for the current image.
        """
        return await self.image_cache.get_metadata()


    async def update_if_needed(self):
        """
        Update the screen image if needed.
        """
        update_needed = False
        meta = await self.get_metadata()
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))
        logger.info(f"Checking update for screen {self.id} now={now.isoformat()} config_mtime={self.config_mtime.isoformat()} meta.expires_at={meta.expires_at if meta else None} meta.last_update_at={meta.last_update_at if meta else None} meta.version={meta.version if meta else None}")
        update_needed = update_needed or meta is None or meta.expires_at is None or meta.last_update_at is None
        update_needed = update_needed or self.config_mtime > meta.last_update_at
        update_needed = update_needed or now > meta.expires_at  #  TODO: does it make sense not to regenerate on every request and use the expires only for controlling the client wakeup?
        if update_needed:
            await self._update()


    async def _update(self):
        """
        Update the screen image.
        """
        logger.info(f"Updating screen {self.id}")
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))

        expires_at, rgb_image = await self._create_image()

        # the version/ETag is the hash of what actually gets served, which
        # the cache computes since it owns that decision (see ImageCache)
        await self.image_cache.put_data(rgb_image, last_update_at=now, expires_at=expires_at,
                                        palette=self.palette)


    @property
    def colors(self) -> tuple[str, str, str]:
        """This screen's (background, primary, accent) color: its own
        fields where set, the global defaults otherwise. The global accent
        is itself optional (clearable in the settings), so a screen/widget
        that also doesn't set one falls back to the global primary -- some
        concrete color has to reach the renderer either way."""
        return self.config.resolved_colors(
            app_config.color_background, app_config.color_primary,
            app_config.color_accent or app_config.color_primary)

    @property
    def palette(self) -> Optional[Palette]:
        """The palette this screen is served in, or None to serve it
        unquantized. An unknown id resolves to None (logged in
        catalog.backend.get_palette()) rather than failing the render: a
        screen that outlives a palette still has to produce an image."""
        return get_palette(self.config.palette_id, self.paths)

    @property
    def panel_label(self) -> str:
        """Compact human label for this screen's panel -- see the free
        function below (usable from a plain ScreenModel, e.g. a screen
        listing that doesn't need a full async Screen instance)."""
        return panel_label(self.config, self.paths)

    async def render_preview(self, boxes: bool = False, raw: bool = False) -> Image.Image:
        """Render this screen fresh for the editor preview, bypassing the
        cache entirely.

        Only for views a display never asks for -- currently the widget
        outlines. They deliberately don't go through the cache: the cached
        image is what displays fetch, and it must not depend on what an
        editor happened to look at. A full render costs on the order of
        ten milliseconds, so re-rendering per preview refresh is cheaper
        than the bookkeeping a third cached variant would need."""
        _, image = await self._create_image(force_bounding_box=boxes)
        palette = None if raw else self.palette
        if palette is None:
            return image
        return await asyncio.to_thread(quantize, image, palette)


    async def _create_image(self, force_bounding_box: bool = False):
        # Draw widgets
        background, primary, accent = self.colors
        image = Image.new(mode="RGB", size=self.config.size, color=background)
        ctx = DrawingContext(image, background, primary, app_config.font,
                             color_accent=accent, paths=self.paths,
                             room=self.room, palette=self.palette)
        ctx.force_bounding_box = force_bounding_box

        next_update = None
        if self.update_schedule:
            next_update = self.update_schedule.get_next_update()

        for w in self.widgets:
            # point the context at this widget's colors before drawing it,
            # the same way origin is set below -- each aspect falls back to
            # the screen's own color independently
            w_primary, w_accent = w.config.resolved_colors(primary, accent)
            if w.config.clipping and w.config.size:
                # draw onto an isolated, size-bounded sub-image instead of
                # the shared canvas: PIL silently drops anything a widget
                # draws beyond an image's own bounds, so this clips
                # overflow instead of letting it bleed into neighbors
                sub_image = Image.new(mode="RGB", size=w.config.size, color=background)
                sub_ctx = DrawingContext(sub_image, background, w_primary, app_config.font,
                                         color_accent=w_accent, paths=self.paths,
                                         room=self.room, palette=self.palette)
                sub_ctx.force_bounding_box = force_bounding_box
                widget_update = await w.draw(sub_ctx)
                image.paste(sub_image, w.config.position)
            else:
                ctx.origin = w.config.position
                ctx.color_primary = w_primary
                ctx.color_accent = w_accent
                widget_update = await w.draw(ctx)
            if widget_update:
                if next_update is None or widget_update < next_update:
                    next_update = widget_update

        return next_update, image


# Reserved id prefix for the auto-generated Room Calendar templates below --
# kept out of paths.screen_dir filenames (a real screen file could never
# collide with it), so get_screen_by_id() can tell "read a file" from "build
# from the panel-type catalog" apart just by looking at the id.
SYNTHETIC_ROOMCALENDAR_PREFIX = "__roomcalendar_"


def _synthetic_roomcalendar_id(width: int, height: int, palette_id: str) -> str:
    return f"{SYNTHETIC_ROOMCALENDAR_PREFIX}{width}x{height}_{palette_id}"


def synthetic_roomcalendar_label(width: int, height: int, palette_id: str) -> str:
    return f"Room Calendar {width}×{height} {palette_id}"


def screens_matching_panel_type(paths: EpaperPaths, panel_type: PanelTypeModel) -> list[str]:
    """Screen ids (real files plus the one matching synthetic Room Calendar
    template, if any) whose width/height/palette_id match panel_type
    exactly -- for restricting a device's Screen select to what its own
    panel can actually show (devicebinding/ui.py, room/simplified_ui.py,
    display/simplified_ui.py). Not enforced anywhere at render time: a
    screen assigned some other way still renders, same as every other
    dangling-reference precedent in this app."""
    matches = []
    for p in sorted(paths.screen_dir.glob('*.json')):
        try:
            config = ScreenModel(**json.loads(p.read_text(encoding='utf-8')))
        except Exception:
            continue  # unreadable/invalid -- not this function's concern to report
        if (config.width, config.height, config.palette_id) == \
                (panel_type.width, panel_type.height, panel_type.palette_id):
            matches.append(p.stem)
    template_id = _synthetic_roomcalendar_id(panel_type.width, panel_type.height, panel_type.palette_id)
    if template_id in synthetic_roomcalendar_screens(paths):
        matches.append(template_id)
    return matches


def synthetic_roomcalendar_screens(paths: EpaperPaths) -> dict[str, ScreenModel]:
    """One auto-generated 'Room Calendar WxH palette' template per distinct
    (width, height, palette_id) in the panel-type catalog: a full-canvas
    RoomCalendarWidget. Any device can be pointed at one of these ids (see
    get_screen_by_id()) and see its own bound room -- no per-room screen file
    needed. Built fresh from the catalog on every call (cheap: a handful of
    in-memory Pydantic models, no I/O beyond what get_panel_types() already
    does) rather than persisted, so they can never drift out of sync with
    panel_types.json."""
    seen: dict[tuple[int, int, str], ScreenModel] = {}
    for panel_type in get_panel_types(paths).values():
        key = (panel_type.width, panel_type.height, panel_type.palette_id)
        if key in seen:
            continue
        widget = RoomCalendarWidgetModel(
            position_x=0, position_y=0,
            size_width=panel_type.width, size_height=panel_type.height,
            date_format_long=None, date_format=None, time_format=None,
        )
        seen[key] = ScreenModel(
            width=panel_type.width, height=panel_type.height,
            palette_id=panel_type.palette_id,
            color_background=panel_type.color_background,
            color_primary=panel_type.color_primary,
            color_accent=panel_type.color_accent,
            widgets=[widget],
        )
    return {_synthetic_roomcalendar_id(w, h, p): screen for (w, h, p), screen in seen.items()}


# cache of screen instances, invalidated by the mtime of the underlying
# screen and schedule files (source of truth stays on disk, so edits via
# the UI as well as direct file changes are picked up). Keyed by (root, id,
# room_id) rather than just (root, id): the same id can exist independently
# under different roots (different nice4iot projects, or standalone), and a
# synthetic Room Calendar template renders differently per room, so two
# devices sharing one template id need their own cache entries.
_screens: dict[tuple[str, str, Optional[str]], Screen] = {}


def _file_mtime(path) -> Optional[datetime.datetime]:
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(path), tz=ZoneInfo("UTC"))
    except OSError:
        return None


def _effective_mtime(paths: EpaperPaths, screen_model_file) -> Optional[datetime.datetime]:
    """The screen's mtime, or the root palette file's if that is newer.

    Everything a screen renders with lives in the screen file itself --
    except the palette, which the screen only references by id. Folding
    palettes.json's mtime in here means an edited palette invalidates
    the screen cache *and* makes update_if_needed() re-render, through
    the mechanism that already exists for an edited screen, with no
    second staleness check anywhere. The palettes shipped in the package
    need no such handling: changing those means a redeploy, hence a
    restart.
    """
    config_mtime = _file_mtime(screen_model_file)
    if config_mtime is None:
        return None
    palette_mtime = _file_mtime(paths.palettes_file)
    if palette_mtime is not None and palette_mtime > config_mtime:
        return palette_mtime
    return config_mtime


def _catalog_mtime(paths: EpaperPaths) -> datetime.datetime:
    """Cache-invalidation mtime for a synthetic Room Calendar template: the
    root's panel_types.json if it overrides/extends the catalog (editing it
    can add, remove or resize a template), else a fixed epoch -- the
    built-in catalog only changes on a redeploy (restart), same reasoning as
    _effective_mtime()'s built-in-palette case."""
    mtime = _file_mtime(paths.panel_types_file)
    return mtime if mtime is not None else datetime.datetime.fromtimestamp(0, tz=ZoneInfo("UTC"))


def _schedule_changed(paths: EpaperPaths, screen: Screen) -> bool:
    schedule_file = paths.schedule_dir / f"{screen.config.update_schedule_id}.json"
    schedule_mtime = _file_mtime(schedule_file)
    if screen.update_schedule is None:
        # reload if the configured schedule file has appeared since
        return schedule_mtime is not None
    return schedule_mtime != screen.update_schedule.config_mtime


async def get_screen_by_id(paths: EpaperPaths, id: str) -> Optional[Screen]:
    """
    Get a screen instance by its id -- or by a device name, resolved to its
    bound screen and room (see devicebinding.backend.resolve_screen_and_room)
    -- reusing a cached instance as long as neither the screen's source (its
    file, or, for a synthetic Room Calendar template, the panel-type
    catalog) nor its schedule file changed. id may also be a synthetic
    template id (SYNTHETIC_ROOMCALENDAR_PREFIX), built from the catalog
    instead of read from paths.screen_dir.
    """
    screen_id, room_id = resolve_screen_and_room(paths, id)
    # re-read on every call, even for a cache hit: a room's fields (notes,
    # booking system, ...) aren't part of config_mtime, so a cached Screen's
    # .room is kept current here rather than frozen at whichever room
    # populated the cache entry first
    room = read_room(paths, room_id) if room_id else None
    cache_key = (str(paths.root), screen_id, room_id)

    config: Optional[ScreenModel] = None
    screen_model_file: Optional[Path] = None
    if screen_id.startswith(SYNTHETIC_ROOMCALENDAR_PREFIX):
        config = synthetic_roomcalendar_screens(paths).get(screen_id)
        config_mtime = _catalog_mtime(paths) if config is not None else None
    else:
        screen_model_file = paths.screen_dir / f"{screen_id}.json"
        config_mtime = _effective_mtime(paths, screen_model_file)

    if config_mtime is None:
        logger.info(f"Screen {screen_id!r} not found")
        _screens.pop(cache_key, None)
        return None

    cached = _screens.get(cache_key)
    if cached is not None and cached.config_mtime == config_mtime and not _schedule_changed(paths, cached):
        cached.room = room
        return cached

    if screen_model_file is not None:
        # (re)load screen model from file
        try:
            async with aiofiles.open(screen_model_file, 'r') as f:
                j = await f.read()
            config = ScreenModel(**json.loads(j))
        except Exception as e:
            logger.info(f"Error reading screen model file {screen_model_file}: {e}")
            _screens.pop(cache_key, None)
            return None
    assert config is not None  # either loaded above, or the synthetic lookup already succeeded

    # create a screen instance
    update_schedule = await get_schedule_by_id(paths, config.update_schedule_id)
    screen = Screen(screen_id, config, config_mtime, paths, update_schedule, room=room)
    _screens[cache_key] = screen

    return screen
