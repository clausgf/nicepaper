from typing import Optional, Tuple

from extensions.epaper.config import app_config
from extensions.epaper.core.datasources.image import get_image
from extensions.epaper.models.screenmodel import ImageWidgetModel
from ..drawingcontext import DrawingContext
from .base import Widget

# error-message box used when the widget has no explicit size to fall back on
_ERROR_DEFAULT_SIZE = (200, 60)


def target_size(image_size: Tuple[int, int],
                size_width: Optional[int], size_height: Optional[int]) -> Tuple[int, int]:
    """Target (width, height) to scale an image to, given the widget's
    configured size. Both set -> exactly that size (may distort); only one set
    -> that dimension with the aspect ratio preserved; neither -> natural size.
    (0, from a cleared ui.number, counts as unset -- same as elsewhere.)"""
    iw, ih = image_size
    if size_width and size_height:
        return (size_width, size_height)
    if size_width:
        return (size_width, max(1, round(ih * size_width / iw)))
    if size_height:
        return (max(1, round(iw * size_height / ih)), size_height)
    return (iw, ih)


class ImageWidget(Widget):

    def __init__(self, id: str, config: ImageWidgetModel):
        super().__init__(id, config)

    async def draw(self, ctx: DrawingContext):
        await super().draw(ctx)
        image = await get_image(ctx.paths, self.config)
        if image is None:
            w, h = (self.config.size_width or _ERROR_DEFAULT_SIZE[0],
                    self.config.size_height or _ERROR_DEFAULT_SIZE[1])
            ctx.draw_text((0, 0), size=(w, h), text=app_config.image_error,
                          font=self.font, ellipsis='...')
            return

        size = target_size(image.size, self.config.size_width, self.config.size_height)
        if size != image.size:
            image = image.resize(size)

        origin = (int(ctx.origin[0]), int(ctx.origin[1]))
        if image.mode in ('RGBA', 'LA', 'P'):
            # composite transparency onto the screen background instead of
            # pasting black where the image is transparent
            image = image.convert('RGBA')
            ctx.img.paste(image, origin, image)
        else:
            ctx.img.paste(image.convert('RGB'), origin)
