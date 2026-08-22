import asyncio
import datetime
import glob
import hashlib
import json
import os
from pathlib import Path
from PIL import Image
from typing import Optional

import aiofiles

from extensions.epaper.catalog.models import Palette
from extensions.epaper.screen.models import ImageMetadata
from extensions.epaper.util import logger


def quantize(rgb_image: Image.Image, palette: Palette) -> Image.Image:
    """The rendered image reduced to a palette, as a display gets it.

    Module-level rather than an ImageCache method because the uncached
    editor preview (Screen.render_preview()) needs exactly the same
    reduction -- a preview quantized differently from the cached image
    would be showing something no display ever gets."""
    logger.info(f"Generating palette image for {palette.id}")
    flat_colors = [value for color in palette.palette for value in color]
    full_palette = flat_colors + [0] * (768 - len(flat_colors))
    palette_img = Image.new("P", (1, 1))
    palette_img.putpalette(full_palette)

    return rgb_image.quantize(palette=palette_img)


class ImageCache:
    """
    A cache for images with metadata, organized by screen name.

    The cache holds the rendered RGB image plus, when the screen has a
    palette, the same image quantized to it. Which of the
    two a display gets is the screen's decision (see screen/backend.py), not
    the request's -- the RGB copy is kept because it is what the editor
    preview shows next to the quantized one, and because re-quantizing it
    is cheaper than re-rendering the screen.

    The cache also owns the version/ETag: it is the hash of the image
    that actually gets served (plus the palette it was quantized with),
    not of the RGB render. That distinction matters -- two screens can
    render identical RGB and still be served different bytes, and a
    palette edited in place would otherwise keep its old ETag while the
    served image changed.
    """

    def __init__(self, base_image_dir: Path, screen_id: str):
        self.screen_id = screen_id
        self.image_dir = os.path.join(base_image_dir, screen_id)
        self.metadata = None
        self.dither = False
        os.makedirs(self.image_dir, exist_ok=True)


    async def put_data(self, rgb_image: Image.Image, last_update_at: datetime.datetime,
                       expires_at: Optional[datetime.datetime],
                       palette: Optional[Palette] = None) -> ImageMetadata:
        """Store a freshly rendered screen and return its metadata."""
        # remove old images
        for filename in glob.glob(os.path.join(self.image_dir, "*.png")):
            os.remove(filename)

        # save new image
        filename = os.path.join(self.image_dir, "rgb.png")
        await asyncio.to_thread(rgb_image.save, filename, format="PNG", compress_level=9)

        # save the quantized image and serve that one, if the screen has a palette
        served_image = rgb_image
        if palette:
            palette_filename = os.path.join(self.image_dir, f"{palette.id}.png")
            served_image = await asyncio.to_thread(
                self._quantize_and_save, rgb_image, palette, palette_filename)

        version = await asyncio.to_thread(self._version, served_image, palette)
        metadata = ImageMetadata(last_update_at=last_update_at, expires_at=expires_at, version=version)

        # save metadata
        self.metadata = metadata
        metadata_filename = os.path.join(self.image_dir, "metadata.json")
        async with aiofiles.open(metadata_filename, 'w') as f:
            j = metadata.model_dump_json(indent=2)
            await f.write(j)
        return metadata


    @staticmethod
    def _version(image: Image.Image, palette: Optional[Palette]) -> str:
        """Hash of the served pixels, plus the palette they mean. A
        quantized image stores palette *indices*, so two different
        palettes can produce byte-identical pixel data (bw and gs4 both
        use indices 0 and 1 for a black-on-white screen) -- mixing the
        palette into the hash keeps their versions apart."""
        h = hashlib.sha256()
        h.update(image.tobytes())
        if palette:
            h.update(repr(palette.palette).encode())
        return h.hexdigest()


    async def get_image_path(self, palette: Optional[Palette] = None) -> Optional[str]:
        """Path of the cached PNG for this palette, or of the RGB image
        when `palette` is None. Quantizes on demand if the palette
        image is missing (e.g. after a palette was added to a screen that
        had already been rendered), so a cache miss costs a quantize
        rather than a full re-render."""
        rgb_filename = os.path.join(self.image_dir, "rgb.png")
        if not os.path.exists(rgb_filename):
            return None

        # return RGB image if no palette is given
        if not palette:
            return rgb_filename

        # return quantized image if a palette is given and exists
        palette_filename = os.path.join(self.image_dir, f"{palette.id}.png")
        if os.path.exists(palette_filename):
            return palette_filename

        rgb_image = await asyncio.to_thread(Image.open, rgb_filename)
        await asyncio.to_thread(self._quantize_and_save, rgb_image, palette, palette_filename)
        return palette_filename


    def _quantize_and_save(self, rgb_image: Image.Image, palette: Palette,
                           palette_filename: str) -> Image.Image:
        palette_image = quantize(rgb_image, palette)
        palette_image.save(palette_filename, format="PNG", bits=8, compress_level=9)
        return palette_image


    async def get_image(self, palette: Optional[Palette] = None) -> Optional[Image.Image]:
        filename = await self.get_image_path(palette)
        if filename is None:
            return None
        return await asyncio.to_thread(Image.open, filename)


    async def get_metadata(self) -> Optional[ImageMetadata]:
        if self.metadata is None:
            metadata_filename = os.path.join(self.image_dir, "metadata.json")
            if not os.path.exists(metadata_filename):
                return None
            async with aiofiles.open(metadata_filename, 'r') as f:
                self.metadata = json.loads(await f.read())
            self.metadata = ImageMetadata(**self.metadata)
        return self.metadata
