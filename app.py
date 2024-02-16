import io
import logging
import os
import threading
import time
from PIL import Image
from plugins import IPlugin
from scrollers import IScroller
from StreamDeck.Devices.StreamDeck import StreamDeck, DialEventType
from typing import List, Optional

class App():

    LOOP_COUNTER_MAX: int = 15

    def __init__(self, deck: Optional[StreamDeck], config: dict) -> None:
        self._plugins: List[IPlugin.IPlugin] = None
        self._active_plugin: Optional[IPlugin.IPlugin] = None
        self._scrollers: List[IScroller.IScroller] = None
        self._home_image: Optional[bytes] = None
        self._render_lock: bool = False
        self._destroyed : bool = False
        self._active_scroller: int = 0
        self._dim_counter: int = 0
        self._loop_counter: int = 0
        self._idle_counter : int = 0
        self._brightness: int = 100
        self._deck: Optional[StreamDeck] = deck
        self._config: dict = config
        self._log: logging.Logger = logging.getLogger(__name__)
        self._log.setLevel(os.environ.get("LOGLEVEL", "INFO"))

        self._next_page_image: Optional[bytes] = None
        self._page_counter : int = 0
        self._num_pages : int = 0

    @property
    def num_buttons(self) -> int:
        if not self._deck_available():
            return 8
        return self._deck.KEY_COUNT

    @property
    def screen_width(self) -> int:
        if self._deck_available():
            return self._deck.TOUCHSCREEN_PIXEL_WIDTH
        return 0

    @property
    def screen_height(self) -> int:
        if self._deck_available():
            return self._deck.TOUCHSCREEN_PIXEL_HEIGHT
        return 0

    @property
    def deck(self) -> Optional[StreamDeck]:
        if self._deck_available():
            return self._deck

    @property
    def home_image(self) -> Optional[bytes]:
        return self._home_image

    @property
    def is_debug_enabled(self) -> bool:
        return self._config.get("debug", False)

    @property
    def creds_path(self) -> str:
        return self._config.get("creds_path", ".creds")

    def set_button_image(self, index: int = 0, image: Optional[bytes] = None) -> None:
        if not self._deck_available():
            return
        self._deck.set_key_image(index, image)

    def load_image(self, path: str, size: int = 100) -> bytes:
        try:
            img = Image.new('RGB', (120, 120), color='black')
            icon = Image.open(path).resize((size, size)).convert("RGBA")
            border = int((120 - size) / 2)
            img.paste(icon, (border, border), icon)
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format = 'JPEG')
            return img_byte_arr.getvalue()
        except Exception as ex: 
            self._log.error(f"Failed to load image '{path}' : {ex}")
            return None

    def run(self) -> None:
        if not self._deck_available():
            self._log.error("No deck found")
            if not self.is_debug_enabled:
                return
        else:
            self._deck.open()
            self._deck.reset()
            self._log.info(f"Opened '{self._deck.deck_type()}' device (serial number: '{self._deck.get_serial_number()}')")

        font : dict = self._config["font"]
        if self._plugins is None:
            plugins : list[IPlugin.IPlugin] = []
            self._log.debug("Loading plugins...")
            for plug in self._config["plugins"]:
                plugin = IPlugin.PluginFactory.create_plugin(self, plug, font)
                plugin.run_as_daemon()
                plugins.append(plugin)
            self._plugins = plugins
            num_plugins = len(self._plugins)
            self._log.info(f"Loaded {num_plugins} plugins")

            # calc num pages
            # We always have a home button
            # We might have a next button
            if num_plugins > self.num_buttons - 1:
                counter : int = 0
                while counter < num_plugins:
                    self._num_pages += 1
                    counter += self.num_buttons - 2
            else:
                self._num_pages = 1

        if self._scrollers is None:
            scrollers : list[IScroller.IScroller] = []
            self._log.debug("Loading scrollers...")
            for scroller in self._config["scrollers"]:
                scroller = IScroller.ScrollerFactory.create_scroller(self, scroller, font)
                scrollers.append(scroller)
            self._scrollers = scrollers
            self._log.info(f"Loaded {len(self._scrollers)} scrollers")

        if self._home_image is None:
            self._home_image = self.load_image("images/home.png")
            self._next_page_image = self.load_image("images/next.png")

        # bind handlers
        if self._deck_available():
            self._deck.set_key_callback(self._key_change_callback)
            self._deck.set_dial_callback(self._dial_change_callback)
            self._deck.set_brightness(self._brightness)

        self._default_layout()
        threading.Thread(target=self._main_loop, daemon=True).start()

    def _render_scroller_image(self, b: bytes) -> None:
        if self._deck is None:
            return
        if self._active_plugin is not None:
            return
        if self._render_lock:
            return
        try:
            self._render_lock = True
            self._deck.set_touchscreen_image(b, 0, 0, self.screen_width, self.screen_height)
        except Exception  as ex:
            self._log.error(ex)
        self._render_lock = False

    def destroy(self) -> bool:
        success = False
        try:
            self._log.debug("Cleaning plugins")
            for plugin in self._plugins:
                plugin.deactivate()
                plugin.destroy()
            self._plugins.clear()
            self._log.debug("Cleaning scrollers")
            for scroller in self._scrollers:
                scroller.deactivate()
            self._scrollers.clear()
            success = True
        except Exception as ex:
            self._log.error(f"Destroy error : {ex}")
        finally:
            self._destroyed = True
            return success

    def _default_layout(self):
        self.set_button_image(0, self._home_image)

        num_plugins : int = len(self._plugins)
        start: int = self._page_counter * (self.num_buttons - 2)

        if self._page_counter == self._num_pages - 1:
            for p in range(start, num_plugins):
                if None == self._plugins[p]:
                    continue
                self.set_button_image(p + 1 - start, self._plugins[p].logo)

            # blank the rest
            for p in range(num_plugins - start + 1, self.num_buttons):
                self.set_button_image(p, None)
        else:
            for p in range(start, start + self.num_buttons - 2):
                if None == self._plugins[p]:
                    continue
                self.set_button_image(p + 1 - start, self._plugins[p].logo)

            # add a next
            self.set_button_image(self.num_buttons - 1, self._next_page_image)

    def _scroll(self):
        if not self._active_plugin:
            if len(self._scrollers) > 0:
                
                scroller = self._scrollers[self._active_scroller]
                if scroller.has_next:
                    self._render_scroller_image(scroller.next())
                else:
                    self._log.debug(f"Setting up scroller : {self._active_scroller + 1}")
                    self._active_scroller += 1
                    if self._active_scroller >= len(self._scrollers):
                        self._active_scroller = 0
                    self._render_scroller_image(self._scrollers[self._active_scroller].generate())

    def _dim(self, brightness_min : int):
        self._brightness = max(brightness_min, self._brightness - 10)
        self._log.debug(f"Dimming to {self._brightness}")
        if self._deck_available():
            self._deck.set_brightness(self._brightness)

    def _main_loop(self):
        self._log.info("Main thread loop starting")

        idle_time_minutes : int = self._config.get("idle_time_minutes", 15)
        idle_step_time : int = (idle_time_minutes * 60) / App.LOOP_COUNTER_MAX
        brightness_dict : dict = self._config.get("brightness", {"minimum": 10})
        brightness_min : int = brightness_dict.get("minimum", 10)
        dim_step_time : int = 300 / App.LOOP_COUNTER_MAX

        self._loop_counter = App.LOOP_COUNTER_MAX
        self._idle_counter = 0
        self._dim_counter = 0

        while not self._destroyed:
            try:
                self._loop_counter += 1
                if self._loop_counter >= App.LOOP_COUNTER_MAX:
                    # 15 secs
                    self._loop_counter = 0
                    self._scroll()
                    self._dim_counter += 1
                    
                    if self._dim_counter >= dim_step_time:
                        # 5 mins
                        self._dim_counter = 0
                        self._dim(brightness_min)
                    
                    if self._active_plugin is not None:
                        if self._active_plugin.idle:
                            self._idle_counter += 1
                            if self._idle_counter >= idle_step_time:
                                self._log.debug("Deactivating plugin because of idle timeout")
                                self._deactivate_plugin()
                        else:
                            self._idle_counter = 0

            except:
                pass
            time.sleep(1.0)

        self._log.info("Main thread loop exiting")

    def _dial_change_callback(self, deck, dial, event, value):
        try:
            if self._active_plugin is None:
                if not value:
                    return
                if event == DialEventType.TURN:
                    match dial:
                        case 1:
                            pass
                        case 2:
                            value = sorted((-1, value, 1))[1]
                            self._active_scroller += value
                            if self._active_scroller >= len(self._scrollers):
                                self._active_scroller = 0
                            elif self._active_scroller < 0:
                                self._active_scroller = len(self._scrollers) - 1
                            self._render_scroller_image(self._scrollers[self._active_scroller].generate())
                        case 3:
                            self._brightness += value * 2
                            self._brightness = max(min(100, self._brightness), 10)
                            self._deck.set_brightness(self._brightness)
                            return
                        case _:
                            pass
                elif event == DialEventType.PUSH:
                    match dial:
                        case 1:
                            pass
                        case 2:
                            pass
                        case 3:
                            if self._brightness < 100:
                                self._brightness = 100
                            else:
                                self._brightness = 10
                            self._deck.set_brightness(self._brightness)
                            return
                        case _:
                            pass
            else:
                if event == DialEventType.PUSH:
                    self._active_plugin.on_dial_pushed(deck, dial, value)
                elif event == DialEventType.TURN:
                    self._active_plugin.on_dial_turned(deck, dial, value)
        except Exception as ex:
            self._log.error(ex)

        self._dim_counter = 0
        self._brightness = 100
        self._deck.set_brightness(self._brightness)

    def _key_change_callback(self, deck, key, key_state):
        try:
            self._log.debug("Key: " + str(key) + " state: " + str(key_state))

            brightness : int = self._brightness
            self._dim_counter = 0
            self._brightness = 100
            self._deck.set_brightness(self._brightness)
            if brightness <= self._config["brightness"]["press_to_wake"]:
                self._log.debug("Setting brightness to 100 and bailing")
                return

            if self._active_plugin is None:
                # key up calls refresh
                if not key_state:
                    self._default_layout()
                    return
                # home key
                if key == 0:
                    self._loop_counter = App.LOOP_COUNTER_MAX
                    self._page_counter = 0
                    return
                # next page key
                if self._page_counter < self._num_pages and key == self.num_buttons - 1:
                    self._page_counter += 1
                    return

                # else we try and kick off a plugin
                start: int = self._page_counter * (self.num_buttons - 2)
                key = key - 1 + start

                # key = key - 1
                if key <= len(self._plugins):
                    self._log.debug(f"Key {key} is in range for an action : {len(self._plugins)} plugins loaded")
                    plugin = self._plugins[key]
                    if plugin:
                        self._log.debug(f"Found plugin : {plugin.name}")
                        # set this before we try and activate it so it blocks scroller images
                        self._active_plugin = plugin
                        if not plugin.activate():
                            self._deactivate_plugin()

            else:
                if 0 == key and key_state:
                    self._log.info("Back button pressed")
                    if self._active_plugin:
                        if not self._active_plugin.handle_back_button():
                            self._deactivate_plugin()
                else:
                    self._active_plugin.on_button_press(deck, key, key_state)

        except Exception as ex:
            self._log.exception('Error in _key_change_callback')

    def _deck_available(self) -> bool:
        return self._deck is not None

    def _deactivate_plugin(self):
        self._log.info("Returning to Home screen")
        if self._active_plugin is not None:
            self._active_plugin.deactivate()
            self._active_plugin = None
        self._loop_counter = App.LOOP_COUNTER_MAX
        self._idle_counter = 0
        self._default_layout()
