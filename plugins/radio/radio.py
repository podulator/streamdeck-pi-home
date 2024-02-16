from ..IPlugin import IPlugin
from ..shared.player.vlc_player import VlcPlayer, VlcPlayerEvents, Track
from enum import IntEnum, auto
import threading
import time

class RadioPlugin(IPlugin):

    class Buttons(IntEnum):
        EXIT = 0
        STATION_1 = auto()
        STATION_2 = auto()
        STATION_3 = auto()
        PREVIOUS = auto()
        STOP = auto()
        PLAY = auto()
        NEXT = auto()

    class ImageKeys(IntEnum):
        BLANK = 0
        PREVIOUS = auto()
        STOP = auto()
        PLAY = auto()
        PLAYING = auto()
        PAUSED = auto()
        NEXT = auto()

    image_keys = [
        "blank.png", 
        "previous.png", 
        "stop.png",
        "play.png",
        "playing.png", 
        "paused.png", 
        "next.png"
    ]

    station_keys = [
        "station-1.png", 
        "station-2.png", 
        "station-3.png",
        "station-4.png",
        "station-5.png",
        "station-6.png",
        "station-7.png"
    ]

    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)
        self._images : list[bytes] = None
        self._bookmark_images : list[bytes] = None
        self._bookmarks : list[dict] = None
        self._info_latch = True
        self._info_callback_lock = False
        self._bookmark_counter : int = 0
        self._running : bool = False
        self._thread : threading.Thread = None
        self._player : VlcPlayer = VlcPlayer(app, self._on_player_callback)

    def activate(self) -> bool:
        try:
            if not super().activate():
                return False

            if self._images is None:
                self._images = []
                self._load_images(self._images, RadioPlugin.image_keys)
        
            self._app.set_button_image(RadioPlugin.Buttons.EXIT, self._app.home_image)

            if self._bookmarks is None:
                # limit to num buttons - 4 nav + home
                self._bookmarks = self._config.get("bookmarks", [])
                self._bookmark_images = []
                self._load_images(self._bookmark_images, RadioPlugin.station_keys)

            num_bookmarks : int = len(self._bookmarks)
            max_bookmarks : int = self._app.num_buttons - 5
            if num_bookmarks > max_bookmarks:
                num_bookmarks = max_bookmarks
            for i in range (1, num_bookmarks + 1):
                self._app.set_button_image(i, self._bookmark_images[i - 1])
            for i in range(num_bookmarks + 1, max_bookmarks + 1):
                self._app.set_button_image(i, self._images[RadioPlugin.ImageKeys.BLANK])

            self._update_buttons()
            self._update_display()

            self._running = True

            if self._thread is None:
                self._thread = threading.Thread(target = self._main_loop)
                self._thread.start()

        except Exception as ex:
            self._log.error(ex)
            self._activated = False

        return self._activated

    def _main_loop(self) -> None:
        self._log.info("Main loop starting")
        counter : int = 0
        while self._running:
            counter += 1
            if counter > 15:
                counter = 0
                self._player.show_now_playing()
            time.sleep(1.0)
        self._log.info("Main loop exiting")

    def _stop_everything(self) -> None:
        try:
            self._running = False
            self._player.stop()
            self._player.clear()
            if self._thread is not None:
                self._thread.join()
                self._thread = None
        except:
            pass

    def deactivate(self):
        super().deactivate()
        if not self._player.playing:
            self._stop_everything()

    def destroy(self):
        super().destroy()
        self._stop_everything()

    def run_as_daemon(self) -> None:
        pass

    def on_button_press(self, deck, key, key_state):
        super().on_button_press(deck, key, key_state)
        if not key_state:
            return

        if key == RadioPlugin.Buttons.PREVIOUS:
            self._bookmark_counter = self._wrap(self._bookmark_counter - 1, len(self._bookmarks))
            self._change_station(self._bookmark_counter)
        elif key == RadioPlugin.Buttons.STOP:
            if self._player.playing:
                self._player.stop()
            self._player.clear()
        elif key == RadioPlugin.Buttons.PLAY:
            if self._player.playing:
                self._player.pause()
            elif self._player.paused:
                self._player.pause()
            else:
                self._change_station(self._bookmark_counter)
        elif key == RadioPlugin.Buttons.NEXT:
            self._bookmark_counter = self._wrap(self._bookmark_counter + 1, len(self._bookmarks))
            self._change_station(self._bookmark_counter)
        else:
            self._bookmark_counter = key - 1
            self._change_station(self._bookmark_counter)

    def on_dial_turned(self, deck, dial, value):
        super().on_dial_turned(deck, dial, value)

        match dial:
            case 0:
                num_bookmarks : int = len(self._bookmarks)
                if num_bookmarks == 0:
                    return
                value = sorted((-1, value, 1))[1]
                self._bookmark_counter = self._wrap(self._bookmark_counter + value, num_bookmarks)
                name : str = self._bookmarks[self._bookmark_counter].get("name", "Unknown")
                msg : str = f"{name} [{self._bookmark_counter + 1}/{num_bookmarks}]"
                self._render(msg)
            case _:
                pass

    def on_dial_pushed(self, deck, dial, state):
        super().on_dial_pushed(deck, dial, state)
        if not state:
            return
        if dial == 0:
            self._change_station(self._bookmark_counter)
        else:
            pass

    @property
    def idle(self) -> bool:
        return self._player.idle

    def _on_player_callback(self, event_type : VlcPlayerEvents, data : dict):
        if not self._running:
            return

        message : str = data.get("message", "")
        keep : bool = data.get("keep", False)
        time : float = data.get("time", 5.0)

        if event_type == VlcPlayerEvents.NONE:
            pass
        elif event_type == VlcPlayerEvents.ERROR_OCCURRED:
            self._log.error(data["message"])
            self._render(message)
            self._update_buttons()        
        elif event_type == VlcPlayerEvents.OPENING_FILE:
            pass
        elif event_type == VlcPlayerEvents.PLAYING_MEDIA:
            self._update_buttons()
        elif event_type == VlcPlayerEvents.PAUSED_MEDIA:
            self._update_buttons()
        elif event_type == VlcPlayerEvents.STOPPED_MEDIA:
            self._update_buttons()
        elif event_type == VlcPlayerEvents.MEDIA_ENDED:
            self._update_buttons()
        elif event_type == VlcPlayerEvents.INFO_MESSAGE:
            try:
                if self._info_callback_lock and not keep:
                    return
                self._info_callback_lock = True
                self._render(message)
                if not self._info_latch or not keep:
                    # restore our original state
                    timer = threading.Timer(time, self._restore_state)
                    timer.start()
                else:
                    self._info_callback_lock = False
            except:
                pass
        else:
            self._log.error(f"Unknow VLC Player event : {event_type}")

    def _update_buttons(self) -> None:
        try:
            self._app.set_button_image(RadioPlugin.Buttons.PREVIOUS, self._images[RadioPlugin.ImageKeys.PREVIOUS])
            self._app.set_button_image(RadioPlugin.Buttons.STOP, self._images[RadioPlugin.ImageKeys.STOP])

            # pause or playing
            if self._player.playing:
                self._app.set_button_image(RadioPlugin.Buttons.PLAY, self._images[RadioPlugin.ImageKeys.PLAYING])
            elif self._player.paused:
                self._app.set_button_image(RadioPlugin.Buttons.PLAY, self._images[RadioPlugin.ImageKeys.PAUSED])
            else:
                self._app.set_button_image(RadioPlugin.Buttons.PLAY, self._images[RadioPlugin.ImageKeys.PLAY])

            self._app.set_button_image(RadioPlugin.Buttons.NEXT, self._images[RadioPlugin.ImageKeys.NEXT])

        except Exception as ex:
            self._log.error(ex)

    def _update_display(self) -> None:
        try:
            if self._player.playing:
                self._player.show_now_playing()
            else:
                self._render(f"{self._name}", self._font["font_size"] / 2)
        except Exception as ex:
            self._log.error(ex)

    def _change_station(self, index : int) -> None:
        try:
            num_bookmarks : int = len(self._bookmarks)
            if index >= num_bookmarks or index < 0:
                self._log.error(f"Invalid bookmark index : {index}")
                return

            if self._player.playing or self._player.paused:
                self._player.stop()
            self._player.clear()

            bm :dict = self._bookmarks[index]
            name : str = bm.get("name", "Unknown")
            url : str = bm.get("url", None)
            if url is None:
                return
            self._log.info(f"Playing : {name} [{self._bookmark_counter + 1}/{num_bookmarks}]")
            track : Track = Track(id = "1", name = name, index = 0, url = url)
            self._player.play(track)
        except Exception as ex:
            self._log.error(ex)
