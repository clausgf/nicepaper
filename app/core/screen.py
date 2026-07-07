import asyncio
import datetime
import hashlib
import json
import os
from zoneinfo import ZoneInfo
from PIL import Image
from typing import Optional
import aiofiles

from app.config import ColorModel, app_config
from app.util import logger
from app.core import widgets
from app.core.drawingcontext import DrawingContext
from app.core.imagecache import ImageCache
from app.core.updateschedule import UpdateSchedule, get_schedule_by_id
from app.models.screenmodel import ImageMetadata, ScreenModel


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

    def __init__(self, id: str, config: ScreenModel, config_mtime: datetime.datetime, update_schedule: Optional[UpdateSchedule] = None):
        self.id = id
        self.config = config
        self.config_mtime = config_mtime
        self.widgets = []
        self.update_schedule = update_schedule
        self.image_cache = ImageCache(self.id)

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
        ctx = DrawingContext(image, app_config.color_background, app_config.color_primary, app_config.font)

        next_update = None
        if self.update_schedule:
            next_update = self.update_schedule.get_next_update()

        for w in self.widgets:
            widget_update = await w.draw(ctx)
            if widget_update:
                if next_update is None or widget_update < next_update:
                    next_update = widget_update

        # for widget in self.widgets:
        #     # Create image
        #     widget_image = Image.new(mode="RGB", size=widget.size, color=0xFFFFFF)
        #     ctx = DrawingContext(widget_image)
        #     widget.draw(ctx)
        #     # Paste image into the main image
        #     image.paste(widget_image, widget.position)

        return next_update, image


# cache of screen instances, invalidated by the mtime of the underlying
# screen and schedule files (source of truth stays on disk, so edits via
# the UI as well as direct file changes are picked up)
_screens: dict[str, Screen] = {}


def _file_mtime(path: str) -> Optional[datetime.datetime]:
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(path), tz=ZoneInfo("UTC"))
    except OSError:
        return None


def _schedule_file(schedule_id: Optional[str]) -> str:
    return os.path.join(app_config.schedule_dir, f"{schedule_id}.json")


def _schedule_changed(screen: Screen) -> bool:
    schedule_mtime = _file_mtime(_schedule_file(screen.config.update_schedule_id))
    if screen.update_schedule is None:
        # reload if the configured schedule file has appeared since
        return schedule_mtime is not None
    return schedule_mtime != screen.update_schedule.config_mtime


async def get_screen_by_id(id: str) -> Optional[Screen]:
    """
    Get a screen instance by its id, reusing a cached instance as long as
    neither the screen file nor its schedule file changed.
    """
    screen_model_file = os.path.join(app_config.screen_dir, f"{id}.json")
    config_mtime = _file_mtime(screen_model_file)
    if config_mtime is None:
        logger.info(f"Screen model file {screen_model_file} not found")
        _screens.pop(id, None)
        return None

    cached = _screens.get(id)
    if cached is not None and cached.config_mtime == config_mtime and not _schedule_changed(cached):
        return cached

    # (re)load screen model from file
    try:
        async with aiofiles.open(screen_model_file, 'r') as f:
            j = await f.read()
        config = ScreenModel(**json.loads(j))
    except Exception as e:
        logger.info(f"Error reading screen model file {screen_model_file}: {e}")
        _screens.pop(id, None)
        return None

    # create a screen instance
    update_schedule = await get_schedule_by_id(config.update_schedule_id)
    screen = Screen(id, config, config_mtime, update_schedule)
    _screens[id] = screen

    return screen
