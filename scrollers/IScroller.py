from . import clock as clock_scroller
from . import cmd as cmd_scroller
from . import date as date_scroller
from . import stocks as stocks_scroller
from . import text as text_scroller
from . import weather as weather_scroller
from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont
from typing import Tuple

import io
import logging
import os

class IScroller(ABC):
    """
    Abstract class for scrollers.
    """

    def __init__(self, app, config, font) -> None:
        super().__init__()
        self._app : object = app
        self._background : Image = None
        self._config : dict = config["config"]
        self._name : str = config["name"]
        self._class : str = config["class"]
        self._font : dict = font
        self._pages : list[:str] = []
        self._page_counter : int = 0
        self._create_background(self._logo_path)
        self._log : logging.Logger = logging.getLogger(__name__)
        self._log.setLevel(os.environ.get("LOGLEVEL", "INFO"))

    @abstractmethod
    def generate(self) -> bytes:
        """
        Abstract method for generating the scroller output.
        """
        self._page_counter = 0
        self._pages.append("Hello, world!")
        if self.has_next:
            return self.next()
        return None

    @abstractmethod
    def deactivate(self) -> None:
        """
        Abstract method for deactivating the scroller.
        """
        self._pages.clear()

    def next(self) -> bytes:
        if self._page_counter >= len(self._pages):
            return None
        result = self._render(self._pages[self._page_counter])
        self._page_counter += 1
        return result

    @property
    def has_next(self) -> bool:
        return self._page_counter < len(self._pages)

    @property
    def name(self) -> str:
        return self._name

    @property
    def _plugin_path(self) -> str:
        dirname = Path(__file__).resolve().parent
        return dirname / self._class

    @property
    def _logo_path(self) -> str:
        logo_path = self._plugin_path / 'images' / 'logo.gif'
        if logo_path.exists():
            return str(logo_path)
        return str(self._plugin_path / 'images' / 'logo.png')

    def _render(self, text) -> bytes:
        x : int = self._app.screen_height + 10
        image : Image = self._background.copy()
        draw : ImageDraw = ImageDraw.Draw(image)

        text : list[str] = text.split('\n')
        num_lines : int = len(text)
        font_size : int = int(self._font["font_size"] / num_lines)
        line_height : int = int((self._app.screen_height - 10) / num_lines)
        line_gap : int = int(20 / num_lines)

        f : FreeTypeFont = ImageFont.truetype(self._font["font_path"], font_size)
        text_width : int = f.getlength(text[0])
        while text_width > (self._app.screen_width - self._app.screen_height - 10) and font_size > 10:
            font_size -= 2
            f = ImageFont.truetype(self._font["font_path"], font_size)
            text_width = f.getlength(text[0])

        if num_lines == 1:
            x = (self._app.screen_width - f.getlength(text[0])) / 2
            if x < self._app.screen_height:
                x = self._app.screen_height
            box : Tuple[int, int, int, int] = f.getbbox(text[0])
            height : int = box[3]
            line_gap += (self._app.screen_height / 2) - (height / 2) - 20

        for i, line in enumerate(text):
            y : int = line_gap + (line_height * i)
            draw.text((x, y), line, font=f, fill=(255, 255, 0))

        img_bytes : io.BytesIO = io.BytesIO()
        image.save(img_bytes, format='JPEG')
        return img_bytes.getvalue()

    def _create_background(self, logo_path) -> Image:
        size : int = 80
        self._background : Image = Image.new(
            mode = "RGB",
            size = (self._app.screen_width, self._app.screen_height),
            color = self._font["background_color"]
        )
        icon : Image = Image.open(logo_path).resize((size, size)).convert("RGBA")
        border : int = int((self._app.screen_height - size) / 2)
        self._background.paste(icon, (border, border), icon)

class ScrollerFactory:

    @staticmethod
    def create_scroller(app, config, font) -> IScroller:

        match config["class"]:
            case "clock":
                return clock_scroller.clock.ClockScroller(app, config, font)
            case "cmd":
                return cmd_scroller.cmd.CmdScroller(app, config, font)
            case "date":
                return date_scroller.date.DateScroller(app, config, font)
            case "stocks":
                return stocks_scroller.stocks.StocksScroller(app, config, font)
            case "text":
                return text_scroller.text.TextScroller(app, config, font)
            case "weather":
                return weather_scroller.weather.WeatherScroller(app, config, font)
            case _:
                return text_scroller.text.TextScroller(app, {
                        "name": "my-greeeting", 
                        "class": "text",
                        "config": {
                            "text": "Unhandled scroller\nClass: " + config["class"]
                        }
                    }, 
                    font
                )
