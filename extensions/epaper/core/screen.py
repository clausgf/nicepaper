import asyncio
import datetime
import hashlib
import json
import os
from zoneinfo import ZoneInfo
from PIL import Image
from typing import Optional
import aiofiles

from extensions.epaper.config import ColorModel, app_config
from extensions.epaper.util import logger
from extensions.epaper.core import widgets
from extensions.epaper.core.drawingcontext import DrawingContext
from extensions.epaper.core.imagecache import ImageCache
from extensions.epaper.core.updateschedule import UpdateSchedule, get_schedule_by_id
from extensions.epaper.models.screenmodel import ImageMetadata, ScreenModel
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
        # create widgets
        for id, widget_config in enumerate(self.config.widgets):
            logger.debug(f"creating widget from {widget_config}")
            widget_classname = widget_config.widget_type + "Widget"

            # get widget class by name
            widget_class = getattr(widgets, widget_classname, None)
            if widget_class is None:
                logger.error(f"Error creating widget: Unknown widget class {widget_classname}")
                continue

            # create widget instance
            widget_obj = widget_class(id, widget_config)
            self.widgets.append(widget_obj)


    async def get_image_path(self, color_model: Optional[ColorModel] = None) -> str:
        """
        Get the current image path for the color model given.
        """
        return await self.image_cache.get_image_path(color_model)


    async def get_image(self, color_model: Optional[ColorModel] = None) -> Image.Image:
        """
        Get the current image for the color model given.
        """
        return await self.image_cache.get_image(color_model)


    async def get_metadata(self) -> ImageMetadata:
        """
        Get the metadata for the current image.
        """
        return await self.image_cache.get_metadata()


    async def update_if_needed(self, color_model: Optional[ColorModel] = None):
        """
        Update the screen image if needed. The color model is just a hint
        to prepare the quantized image in the cache in advance.
        """
        update_needed = False
        meta = await self.get_metadata()
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))
        logger.info(f"Checking update for screen {self.id} now={now.isoformat()} config_mtime={self.config_mtime.isoformat()} meta.expires_at={meta.expires_at if meta else None} meta.last_update_at={meta.last_update_at if meta else None} meta.version={meta.version if meta else None}")
        update_needed = update_needed or meta is None or meta.expires_at is None or meta.last_update_at is None
        update_needed = update_needed or self.config_mtime > meta.last_update_at
        update_needed = update_needed or now > meta.expires_at  #  TODO: does it make sense not to regenerate on every request and use the expires only for controlling the client wakeup?
        if update_needed:
            await self._update(color_model)


    async def _update(self, color_model: Optional[ColorModel] = None):
        """
        Update the screen image.
        """
        logger.info(f"Updating screen {self.id}")
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))

        expires_at, rgb_image = await self._create_image()

        # create a hash of the raw pixel data as version/etag
        version = await asyncio.to_thread(
            lambda: hashlib.sha256(rgb_image.tobytes()).hexdigest())

        meta = ImageMetadata(last_update_at=now, expires_at=expires_at, version=version)
        await self.image_cache.put_data(rgb_image, meta, color_model)


    async def _create_image(self):
        # Draw widgets
        image = Image.new(mode="RGB", size=self.config.size, color=app_config.color_background)
        ctx = DrawingContext(image, app_config.color_background, app_config.color_primary, app_config.font, paths=self.paths)

        next_update = None
        if self.update_schedule:
            next_update = self.update_schedule.get_next_update()

        for w in self.widgets:
            if w.config.clipping and w.config.size:
                # draw onto an isolated, size-bounded sub-image instead of
                # the shared canvas: PIL silently drops anything a widget
                # draws beyond an image's own bounds, so this clips
                # overflow instead of letting it bleed into neighbors
                sub_image = Image.new(mode="RGB", size=w.config.size, color=app_config.color_background)
                sub_ctx = DrawingContext(sub_image, app_config.color_background, app_config.color_primary,
                                          app_config.font, paths=self.paths)
                widget_update = await w.draw(sub_ctx)
                image.paste(sub_image, w.config.position)
            else:
                ctx.origin = w.config.position
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


def _schedule_changed(paths: EpaperPaths, screen: Screen) -> bool:
    schedule_file = paths.schedule_dir / f"{screen.config.update_schedule_id}.json"
    schedule_mtime = _file_mtime(schedule_file)
    if screen.update_schedule is None:
        # reload if the configured schedule file has appeared since
        return schedule_mtime is not None
    return schedule_mtime != screen.update_schedule.config_mtime


async def get_aliases(paths: EpaperPaths) -> dict[str, str]:
    """
    All entries in the alias file (name -> screen id), or {} if the file
    doesn't exist or can't be parsed. Shared by _resolve_alias() below and
    the device-config UI card (ui/panels.py's device_config_card), which
    lets a nice4iot device be assigned a screen by writing an alias keyed
    by the device's own name.
    """
    if not paths.alias_file.exists():
        return {}
    try:
        async with aiofiles.open(paths.alias_file, 'r') as f:
            return json.loads(await f.read())
    except (OSError, ValueError) as e:
        logger.warning(f"Error reading alias file {paths.alias_file}: {e}")
        return {}


async def set_alias(paths: EpaperPaths, name: str, screen_id: Optional[str]) -> None:
    """Set (screen_id given) or remove (screen_id=None) a single alias entry."""
    aliases = await get_aliases(paths)
    if screen_id is None:
        aliases.pop(name, None)
    else:
        aliases[name] = screen_id
    async with aiofiles.open(paths.alias_file, 'w') as f:
        await f.write(json.dumps(aliases, indent=2))


async def _resolve_alias(paths: EpaperPaths, id: str) -> str:
    """
    Resolve a display alias to its target screen id, e.g. so a display
    can be addressed as "hallway" instead of the screen file name. Falls
    back to the given id unchanged if there is no matching entry.
    """
    aliases = await get_aliases(paths)
    return aliases.get(id, id)


async def get_screen_by_id(paths: EpaperPaths, id: str) -> Optional[Screen]:
    """
    Get a screen instance by its id (or by an alias resolved via the
    alias file), reusing a cached instance as long as neither the screen
    file nor its schedule file changed.
    """
    id = await _resolve_alias(paths, id)
    cache_key = (str(paths.root), id)
    screen_model_file = paths.screen_dir / f"{id}.json"
    config_mtime = _file_mtime(screen_model_file)
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
