import io
import logging
import os
import textwrap

from abc import ABC
from pathlib import Path
from PIL import Image,ImageDraw, ImageFont
from . import blank as blank_plugin
from . import bluetooth as bluetooth_plugin
from . import firetv as firetv_plugin
from . import hue as hue_plugin
from . import jellyfin as jellyfin_plugin
from . import levoit as levoit_plugin
from . import radio as radio_plugin
from . import settings as settings_plugin
from . import subsonic as subsonic_plugin
from . import tado as tado_plugin
from . import velux as velux_plugin
import time

class IPlugin(ABC):

    RenderLock : bool = False
    LongPressDelta : float = 1.0

    def __init__(self, app, config, font) -> None:
        super().__init__()
        self._activated : bool = False
        self._app = app
        self._logo : bytes= None
        self._back_button : bytes = None
        self._font : dict = font
        self._config : dict = config["config"]
        self._name : str = config["name"]
        self._class : str = config["class"]
        self._cache : dict = None
        self._log : logging.Logger = logging.getLogger(__name__)
        self._log.setLevel(os.environ.get("LOGLEVEL", "INFO"))
        self._help_message : str = "This is a default help message\nPlease override me\nin your own plugin"
        self._help_showing : bool = False

    def activate(self) -> bool:
        try:
            self._activated = True
            self._render(f"Loading {self._name}", self._font["font_size"] / 2)
            self._log.info(f"{self._class} :: activated")
            self._app.set_button_image(0, self.back_button)
            # clear others
            for n in range(1, self._app.num_buttons):
                self._app.set_button_image(n, None)
        except Exception as ex:
            self._log.error(f"Error activating plugin: {ex}")
            self._activated = False

        return self._activated

    def deactivate(self):
        self._log.info(f"{self._class} :: deactivated")
        self._activated = False

    def destroy(self):
        self._log.info(f"{self._class} :: destroyed")

    def run_as_daemon(self) -> None:
        self._log.info(f"{self._class} :: running as daemon")

    def on_button_press(self, deck, key, key_state):
        self._log.debug(f"{self._name} :: {self._class} :: handling key: {key} state: {key_state}")

    def on_dial_turned(self, deck, dial, value):
        self._log.debug(f"{self._name} :: {self._class} :: handling dial turn: {dial} value: {value}")
    
    def on_dial_pushed(self, deck, dial, state):
        self._log.debug(f"{self._name} :: {self._class} :: handling dial push: {dial} state: {state}")

    @property
    def idle(self) -> bool:
        return True

    def handle_back_button(self) -> bool:
        """
        Returns True when it has nested pages, and pops the page. 
        Default is to return False, and the app can deactivate the plugin.
        """
        return False

    def show_help(self) -> None:
        self._log.info("showing help")
        cache : dict = self._cache
        self._render(self._help_message)
        self._cache = cache
        self._help_showing = True

    def hide_help(self) -> None:
        self._log.info("hiding the help")
        if self._cache:
            self._render(
                self._cache["text"], 
                self._cache["font_size"], 
                self._cache["font_path"], 
                self._cache["bg_color"]
            )
        else:
            self._render("")
        self._help_showing = False

    @property
    def help_showing(self) -> bool:
        return self._help_showing

    def _load_images(self, collection, keys):
        for image in keys:
            collection.append(self._app.load_image(f"{self._plugin_path}/images/{image}"))

    def _wrap(self, index, length):
        if length == 0:
            return 0
        return (index + length) % length

    def _render(self, text : str, font_size : int = -1, font_path : str = "", bg_color : str = "black") -> bool:
        if not self._activated:
            return False
        if self._app.deck is None:
            return False
        if IPlugin.RenderLock:
            return False
        success : bool = False
        try:
            IPlugin.RenderLock = True
            if font_size < 0:
                font_size = self._font["font_size"]
            if not font_path:
                font_path = self._font["font_path"]

            # set the cache
            self._cache = {
                "text": text,
                "font_size": font_size, 
                "font_path": font_path, 
                "bg_color": bg_color
            }

            b : bytes = self._text_to_image(text, font_size, font_path, bg_color)
            self._app.deck.set_touchscreen_image(b, 0, 0, self._app.screen_width, self._app.screen_height)
            success = True
        except Exception as ex:
            self._log.error(ex)
        IPlugin.RenderLock = False
        return success

    def _text_to_image(self, text : str, font_size : int, font_path : str, bg_color : str) -> bytes:
        try:
            image = Image.new(mode = "RGB", size = (self._app.screen_width, self._app.screen_height), color = bg_color)
            draw = ImageDraw.Draw(image)

            text_lines = text.split('\n')
            num_lines : int = len(text_lines)
            align_centre : bool = num_lines == 1
            font_size = int(font_size / num_lines)

            if not align_centre:
                f = ImageFont.truetype(font_path, font_size)
                x = 10
                line_height = int((self._app.screen_height - 10) / num_lines)
                line_gap = int(20 / num_lines)
                for i in range(0, num_lines):
                    y = line_gap + (line_height * i)
                    draw.text((x, y), text_lines[i], font = f, fill = (255, 255, 0))
            else:
                max_length : int = 28
                lines : list[str] = []
                delim_starts : list[str] = [ "(", "[", " - " , " | " ]
                delim_ends : list[str] = [ ")", "]", " - ", " | " ]
                marker : str = "_"
                start_markers : list[str] = []
                end_markers : list[str] = []

                text = text.replace(marker, " ")
                for i in range(len(delim_starts)):
                    start_marker : str = marker + delim_starts[i]
                    end_marker : str = delim_ends[i] + marker
                    text = text.replace(delim_starts[i], start_marker)
                    text = text.replace(delim_ends[i], end_marker)
                    start_markers.append(start_marker)
                    end_markers.append(end_marker)

                #self._log.debug(f"Pre-processed : {text}")

                parts = text.split(marker)[:5]
                if len(parts) > 1:
                    for p in parts:
                        p = p.strip()
                        found : bool = False
                        for i, m in enumerate(start_markers):
                            if p == delim_starts[i].strip() or p == delim_ends[i].strip():
                                found = True
                                break
                            if p.startswith(m) and p.endswith(end_markers[i]):
                                found = True
                                lines.append(p)
                        if not found:
                            lines.append(p)
                else:
                    lines = textwrap.wrap(text, width = max_length, break_long_words = False)

                # limit it to 3 rows
                lines = lines[:3]
                num_lines : int = len(lines)
                line_height : int = int( self._app.screen_height / num_lines )
                font_size : int = int(font_size / num_lines)
                total_height : int = 0
                # get the max size that works
                for line in lines:
                    f = ImageFont.truetype(font_path, font_size)
                    text_width = f.getlength(line)
                    while text_width > self._app.screen_width and font_size > 10:
                        font_size -= 2
                        f = ImageFont.truetype(font_path, font_size)
                        text_width = f.getlength(line)
                    box = f.getbbox(line)
                    total_height += (box[3])

                f = ImageFont.truetype(font_path, font_size)
                half_avg_height : int = (total_height / num_lines) / 2
                half_line_height : int = line_height / 2
                for i, line in enumerate(lines):
                    text_width = f.getlength(line)
                    x = (self._app.screen_width - text_width) / 2
                    y = (line_height * i) + half_line_height - half_avg_height
                    draw.text((x, y), line, font = f, fill = (255, 255, 0))

            img_bytes = io.BytesIO()
            image.save(img_bytes, format='JPEG')
            return img_bytes.getvalue()
        except Exception as ex:
            raise Exception(f"Error converting text to image: {ex}")

    @property
    def name(self):
        return self._name

    @property 
    def _plugin_path(self):
        dirname = Path(__file__).resolve().parent
        return dirname / self._class

    @property
    def _logo_path(self):
        logo_path = Path(self._plugin_path) / "images" / "logo.gif"
        if logo_path.exists():
            return logo_path
        return Path(self._plugin_path) / "images" / "logo.png"
    
    @property
    def logo(self) -> bytes:
        if self._logo is None:
            self._logo = self._app.load_image(self._logo_path, 100)
        return self._logo

    @property
    def _back_button_path(self):
        dirname = Path(__file__).resolve().parent
        return dirname / "images" / "back.png"

    @property
    def back_button(self):
        if self._back_button is None:
            self._back_button = self._app.load_image(self._back_button_path, 100)
        return self._back_button

    @property
    def config(self) -> dict:
        return self._config

class PluginFactory:

    @staticmethod
    def create_plugin(app, config, font) -> IPlugin:
        match config["class"]:
            case "blank":
                return blank_plugin.blank.BlankPlugin(app, config, font)
            case "bluetooth":
                return bluetooth_plugin.bluetooth.BluetoothPlugin(app, config, font)
            case "firetv":
                return firetv_plugin.firetv.FireTvPlugin(app, config, font)
            case "hue":
                return hue_plugin.hue.HuePlugin(app, config, font)
            case "jellyfin":
                return jellyfin_plugin.jellyfin.JellyfinPlugin(app, config, font)
            case "levoit":
                return levoit_plugin.levoit.LevoitPlugin(app, config, font)
            case "radio":
                return radio_plugin.radio.RadioPlugin(app, config, font)
            case "settings":
                return settings_plugin.settings.SettingsPlugin(app, config, font)
            case "subsonic":
                return subsonic_plugin.subsonic.SubsonicPlugin(app, config, font)
            case "tado":
                return tado_plugin.tado.TadoPlugin(app, config, font)
            case "velux":
                return velux_plugin.velux.VeluxPlugin(app, config, font)
        return None
