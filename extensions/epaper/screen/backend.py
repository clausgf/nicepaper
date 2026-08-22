import asyncio
import datetime
import json
import os
from zoneinfo import ZoneInfo
from PIL import Image
from typing import Optional
import aiofiles

from extensions.epaper.catalog.backend import get_palette, get_panel_type
from extensions.epaper.util import logger
from extensions.epaper.core import widgets
from extensions.epaper.devicebinding.backend import resolve_screen_id
from extensions.epaper.core.drawingcontext import DrawingContext
from extensions.epaper.core.imagecache import ImageCache, quantize
from extensions.epaper.global_config.backend import app_config
from extensions.epaper.catalog.models import Palette
from extensions.epaper.schedule.backend import UpdateSchedule, get_schedule_by_id
from extensions.epaper.screen.models import ImageMetadata, ScreenModel
from extensions.epaper.paths import EpaperPaths


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
                 paths: EpaperPaths, update_schedule: Optional[UpdateSchedule] = None):
        self.id = id
        self.config = config
        self.config_mtime = config_mtime
        self.paths = paths
        self.widgets = []
        self.update_schedule = update_schedule
        self.image_cache = ImageCache(paths.image_dir, self.id)

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
        """Compact human label for this screen's panel: the applied panel
        type's own name + GxEPD2 class when panel_type_id is set and still
        resolves in the catalog; otherwise (no preset, or a dangling id) a
        plain summary of the screen's own size and palette -- the screen
        itself carries no GxEPD2 class, only a panel-type preset does, so
        the fallback has none either. The editor is responsible for
        clearing panel_type_id once the screen's fields no longer match the
        preset it names (see screen/ui.py's on_field_change), so a resolved
        panel type here can be trusted to describe this screen."""
        panel_type = get_panel_type(self.config.panel_type_id, self.paths)
        if panel_type is not None:
            return f'{panel_type.name} {panel_type.gxepd2_class or ""}'.strip()
        parts = [f'{self.config.width}x{self.config.height}']
        if self.config.palette_id:
            palette = self.palette
            parts.append(f'{self.config.palette_id} {len(palette.palette)}-color'
                        if palette is not None else self.config.palette_id)
        return ' '.join(parts)

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
                             color_accent=accent, paths=self.paths)
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
                                         color_accent=w_accent, paths=self.paths)
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


# cache of screen instances, invalidated by the mtime of the underlying
# screen and schedule files (source of truth stays on disk, so edits via
# the UI as well as direct file changes are picked up). Keyed by (root,
# id) rather than just id, since the same id can exist independently
# under different roots (different nice4iot projects, or standalone).
_screens: dict[tuple[str, str], Screen] = {}


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


def _schedule_changed(paths: EpaperPaths, screen: Screen) -> bool:
    schedule_file = paths.schedule_dir / f"{screen.config.update_schedule_id}.json"
    schedule_mtime = _file_mtime(schedule_file)
    if screen.update_schedule is None:
        # reload if the configured schedule file has appeared since
        return schedule_mtime is not None
    return schedule_mtime != screen.update_schedule.config_mtime


async def get_screen_by_id(paths: EpaperPaths, id: str) -> Optional[Screen]:
    """
    Get a screen instance by its id (or by a device name resolved to its
    bound screen, see devicebinding.backend.resolve_screen_id), reusing a
    cached instance as long as neither the screen file nor its schedule
    file changed.
    """
    id = resolve_screen_id(paths, id)
    cache_key = (str(paths.root), id)
    screen_model_file = paths.screen_dir / f"{id}.json"
    config_mtime = _effective_mtime(paths, screen_model_file)
    if config_mtime is None:
        logger.info(f"Screen model file {screen_model_file} not found")
        _screens.pop(cache_key, None)
        return None

    cached = _screens.get(cache_key)
    if cached is not None and cached.config_mtime == config_mtime and not _schedule_changed(paths, cached):
        return cached

    # (re)load screen model from file
    try:
        async with aiofiles.open(screen_model_file, 'r') as f:
            j = await f.read()
        config = ScreenModel(**json.loads(j))
    except Exception as e:
        logger.info(f"Error reading screen model file {screen_model_file}: {e}")
        _screens.pop(cache_key, None)
        return None

    # create a screen instance
    update_schedule = await get_schedule_by_id(paths, config.update_schedule_id)
    screen = Screen(id, config, config_mtime, paths, update_schedule)
    _screens[cache_key] = screen

    return screen
