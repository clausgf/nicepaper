import glob
import json
import os
from PIL import Image
from typing import Optional

import aiofiles

from app.config import ColorModel, app_config
from app.models.screenmodel import ImageMetadata
from app.util import logger


class ImageCache:
    """
    A cache for images with metadata. The cache is organized by screen name.
    The cache holds RGB images and their metadata. The cache can be queried
    for a specific color model, which will return a quantized image with the
    right palette.
    """

    def __init__(self, screen_id: str):
        self.screen_id = screen_id
        self.image_dir = os.path.join(app_config.image_dir, screen_id)
        self.metadata = None
        self.dither = False
        os.makedirs(self.image_dir, exist_ok=True)


    async def put_data(self, rgb_image: Image.Image, metadata: ImageMetadata, color_model: Optional[ColorModel] = None):
        # remove old images
        for filename in glob.glob(os.path.join(self.image_dir, "*.png")):
            os.remove(filename)

        # save new image
        filename = os.path.join(self.image_dir, "rgb.png")
        rgb_image.save(filename, format="PNG", compress_level=9)

        # save metadata
        self.metadata = metadata
        metadata_filename = os.path.join(self.image_dir, "metadata.json")
        async with aiofiles.open(metadata_filename, 'w') as f:
            j = metadata.model_dump_json(indent=2)
            await f.write(j)

        # save quantized images
        if color_model:
            palette_image = await self._generate_palette_image(rgb_image, color_model)
            palette_filename = os.path.join(self.image_dir, f"{color_model.id}.png")
            palette_image.save(palette_filename, format="PNG", compress_level=9)


    async def get_image_path(self, color_model: Optional[ColorModel] = None) -> str:
        rgb_filename = os.path.join(self.image_dir, "rgb.png")
        if not os.path.exists(rgb_filename):
            return None

        # return RGB image if no color model is given
        if not color_model:
            return rgb_filename

        # return quantized image if color model is given and exists
        palette_filename = os.path.join(self.image_dir, f"{color_model.id}.png")
        if os.path.exists(palette_filename):
            return palette_filename
        
        rgb_image = Image.open(rgb_filename)
        palette_image = await self._generate_palette_image(rgb_image, color_model)
        palette_image.save(palette_filename, format="PNG", compress_level=9)
        return palette_filename
        

    async def _generate_palette_image(self, rgb_image: Image.Image, color_model: ColorModel) -> Image.Image:
        logger.info(f"Generating palette image for {color_model.id}")
        # generate image with the right color model
        palette = [value for color in color_model.palette for value in color]
        full_palette = palette + [0] * (768-len(palette))
        palette_img = Image.new("P", (1, 1))
        palette_img.putpalette(full_palette)

        return rgb_image.quantize(palette=palette_img)


    async def get_image(self, color_model: Optional[ColorModel] = None) -> Image:
        filename = await self.get_image_path(color_model)
        if filename is None:
            return None
        return Image.open(filename)


    async def get_metadata(self) -> ImageMetadata:
        if self.metadata is None:
            metadata_filename = os.path.join(self.image_dir, "metadata.json")
            if not os.path.exists(metadata_filename):
                return None
            async with aiofiles.open(metadata_filename, 'r') as f:
                self.metadata = json.loads(await f.read())
            self.metadata = ImageMetadata(**self.metadata)
        return self.metadata
