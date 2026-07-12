import os
import math
from typing import Tuple
from PIL import Image, ImageFont, ImageDraw, ImageColor

from extensions.epaper.util import logger
from extensions.epaper.config import app_config


class FontResourceManager:
    cache = {}

    def __init__(self, base_path):
        self.base_path = base_path

    def get(self, name, fontsize):
        # Load from cache
        font = self.cache.get((name, fontsize))
        if font is not None:
            return font

        # Create new font
        fontpath = os.path.join(self.base_path, name)
        if not os.path.exists(fontpath):
            raise FileNotFoundError(f"Font file not found: {fontpath}")

        logger.debug(f"Loading font: {fontpath} {fontsize}")
        if fontpath.endswith('.ttf'):
            font = ImageFont.truetype(fontpath, fontsize)
        elif fontpath.endswith('.pil'):
            font = ImageFont.load(fontpath)
        else:
            raise ValueError(f"Unsupported font file type: {fontpath}")
        self.cache[(name, fontsize)] = font

        return font


font_resource_manager = FontResourceManager(app_config.font_path)


class IconResourceManager:
    cache = {}

    def __init__(self, base_path):
        self.base_path = base_path

    def get(self, name):
        image = IconResourceManager.cache.get(name)
        if image is not None:
            return image

        image = Image.open(os.path.join(self.base_path, name))
        IconResourceManager.cache[name] = image

        return image


icon_resource_manager = IconResourceManager(app_config.icon_path)


class DrawingContext:

    def __init__(self, image, color_background: Tuple[int, int, int], color_primary: Tuple[int, int, int], font_model, paths=None):
        self.img = image
        self.draw = ImageDraw.Draw(image)
        self.font_provider = font_resource_manager
        self.icon_provider = icon_resource_manager
        self.color_background = color_background
        self.color_primary = color_primary
        self.font_model = font_model
        self.font = self.get_font(font_model[0], font_model[1])
        self.origin = (0,0)
        self.size = image.size
        # per-root file locations (screens/schedules/ical cache/...), so
        # widgets that need to read/write files (e.g. RoomCalendarWidget's
        # ical cache) work the same standalone and as a nice4iot extension
        self.paths = paths


    def get_font(self, name, size):
        return self.font_provider.get(name, size)


    def get_icon(self, name):
        return self.icon_provider.get(name)


    def draw_icon_centered(self, xy, name):
        image = self.get_icon(name)
        x = math.floor(self.origin[0] + xy[0] - image.width / 2)
        y = math.floor(self.origin[1] + xy[1] - image.height / 2)
        self.img.paste(image, (x, y))
        return image.size


    def draw_line(self, xys, *args, **params):
        xys = tuple( (self.origin[0] + xy[0], self.origin[1] + xy[1]) for xy in xys )
        self.draw.line( xys, *args, **params)


    def textsize(self, text: str, font ,mode: str | None = None):
        if mode:      
            size_img = Image.new(mode, self.size)
            size_draw = ImageDraw.Draw(size_img)
            _, _, width, height = size_draw.textbbox((0,0), text, font)
        else:
            _, _, width, height = self.draw.textbbox((0,0), text, font)
        return width, height


    def draw_text_centered_xy(self, xy, text, font, **params):
        _, _, width, height = self.draw.textbbox((0,0), text, font)
        x,  y  = math.floor(xy[0] - width/2), math.floor(xy[1] - height/2)
        return self.draw_text_xy( (x, y), text, font, **params)


    def draw_text_xy(self, xy, text, font, **params):
        params['fill'] = params.get( 'fill', self.color_primary )
        x, y = self.origin[0] + xy[0], self.origin[1] + xy[1]

        _, _, width, height = self.draw.textbbox((0,0), text, font)
        mask = Image.new("1", (width, height), color=0)
        draw = ImageDraw.Draw(mask)
        draw.text((0, 0), text, font=font, fill=1)
        image = Image.new(self.img.mode, (width, height), color=params['fill'])
        self.img.paste(image, (x,y), mask=mask)
        #f = params['fill']
        #print(f"xy={xy}  text={text}  fill={f}")

        #self.draw.text((x, y), text, font=font, **params)
        return width, height


    def draw_text(self, position, size, text, 
                  alignment='lt', font=None, color=None, 
                  multiline: bool = False, ellipsis: str = None):
        """
        Draw the text into the context's coordinate system.

        :param position: The position of the text relativ to the context's origin.
        :param size: None or the size of the text box. This is used for alignment and 
            optional ellipsis if the text does not fit.
        :param text: The text to draw.
        :param alignment: The alignment of the text within the box. The first character 
            is the horizontal alignment [lcr], the second the vertical alignment [tcb].
            These parameters are translated to Pillow's text alignment parameter.
        :param font: The font to use.
        :param color: The color to use.
        :param multiline: If True, the text is split into multiple lines if it does not fit.
        :param ellipsis: The string to append to the text if it does not fit.

        :return: The size of the text's bounding box.
        """
        # parameter check plus ellipsis and multiline handling
        if font is None:
            font = self.font
        if color is None:
            color = self.color_primary
        if (multiline or ellipsis is not None) and not size:
            raise ValueError("Multiline or ellipsis require a size parameter.")
        if ellipsis is not None:
            text = self._ellipsis(size, text, font, ellipsis)
        if multiline:
            lines = self._multiline_text(size, text, font)
            text = "\n".join(lines)
        if size is None:
            size = (0, 0)

        # align/position the text inside the box
        width, height = self.textsize(text, font,"1")
        if alignment[0] == 'l':
            x = self.origin[0] + position[0]
        elif alignment[0] == 'c':
            x = self.origin[0] + position[0] + (size[0] - width) // 2
        elif alignment[0] == 'r':
            x = self.origin[0] + position[0] + size[0] - width
        else:
            raise ValueError(f"Invalid alignment value: {alignment[0]}")
        
        if alignment[1] == 't':
            y = self.origin[1] + position[1]
        elif alignment[1] == 'c':
            y = self.origin[1] + position[1] + (size[1] - height) // 2
        elif alignment[1] == 'b':
            y = self.origin[1] + position[1] + size[1] - height
        else:
            raise ValueError(f"Invalid alignment value: {alignment[1]}")

        # draw monochrome text and paste it into the image with the desired color
        mask = Image.new("1", (width, height))
        d = ImageDraw.Draw(mask)
        d.text((0, 0), text, font=font, fill=1, align='la')
        color_layer = Image.new("RGB", (width, height), color=color)
        self.img.paste(color_layer, (x, y), mask=mask)

        return width, height

    def _ellipsis(self, size, text: str, font, ellipsis: str) -> str:
        width, _ = self.textsize(text, font)
        if width <= size[0]:
            return text
        width_ellipsis, _ = self.textsize(ellipsis, font)
        if width_ellipsis > size[0]:
            raise ValueError("Ellipsis does not fit into the text box.")
        width_max = size[0] - width_ellipsis
        for i in range(1, len(text)):
            width, _ = self.textsize(text[:i], font)
            if width > width_max:
                return text[:i-1] + ellipsis
        return text
    
    def _multiline_text(self, size, text, font):
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            w, _ = self.textsize(lines[i], font)
            if w > size[0]:
                # split line at last possible space
                l, r = lines[i], ''
                while w > size[0] and ' ' in l:
                    l, _, r_new = l.rpartition(" ")
                    r = r_new if not r else r_new + " " + r
                    w, _ = self.textsize(l, font)
                if r:
                    lines[i] = l
                    lines.insert(i+1, r)
            i += 1
        return lines
