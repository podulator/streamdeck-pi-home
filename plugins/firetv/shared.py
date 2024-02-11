from ..IPlugin import IPlugin
from abc import ABC, abstractmethod
from enum import IntEnum, auto

import json
import operator
import threading

# https://gist.github.com/arjunv/2bbcca9a1a1c127749f8dcb6d36fb0bc
class FireTvKeyCommands(IntEnum):
    HOME = 3
    BACK = 4
    DPAD_UP = 19
    DPAD_DOWN = 20
    DPAD_LEFT = 21
    DPAD_RIGHT = 22
    SELECT = 23
    #VOLUME_UP = 24
    #VOLUME_DOWN = 25
    POWER = 26  # always turns on
    MENU = 82
    PLAY_PAUSE = 85
    STOP = 86
    NEXT = 87
    PREVIOUS = 88
    REWIND = 89
    FAST_FORWARD = 90
    #MIC_MUTE = 91
    #VOLUME_MUTE = 164
    BEGIN_PAIRING = 165
    TV_CHANNEL_UP = 166
    TV_CHANNEL_DOWN = 167
    TV_INPUT = 170
    SHORTCUT_1 = 188    # set to change to hdmi input
    SEARCH_BLUETOOTH = 190
    SLEEP = 223
    WAKE_UP = 224
    ACTIVATE_ALEXA = 259
    SOFT_SLEEP = 276

class IChildPlugin(ABC):

    def __init__(self, parent : IPlugin) -> None:
        self._parent : IPlugin = parent
        self._activated : bool = False

    def activate(self) -> bool:
        self._activated = True

    def deactivate(self) -> bool:
        self._activated = False

    def on_button_press(self, key, key_state) -> bool:
        if(not self._activated): return False
        self._parent._log.debug(f"on_button_press :: key = {key}, state = {key_state}")
        return True

    def on_dial_turned(self, dial, value) -> bool:
        if(not self._activated): return False
        self._parent._log.debug(f"on_dial_turned :: dial = {dial}, value = {value}")
        return True

    def on_dial_pushed(self, dial, state) -> bool:
        if(not self._activated): return False
        self._parent._log.debug(f"on_dial_pushed :: dial = {dial}, state = {state}")
        return True

    def status(self) -> str:
        return "Activated" if self._activated else "Deactivated"

    def update_buttons(self) -> bool:
        if(not self._activated): return False
        return True

class MediaControlsPlugin(IChildPlugin):

    NOTHING_PLAYING : str = "Nothing selected"

    class State(IntEnum):
        NONE = 0
        REWINDING = auto()
        PLAYING = auto()
        PAUSED = auto()
        FORWARDING = auto()

    class Buttons(IntEnum):
        BACK = 0
        MUTE = auto()
        PREVIOUS = auto()
        NEXT = auto()

        REWIND = auto()
        STOP = auto()
        PLAY = auto()
        FORWARD = auto()

    class ImageKeys(IntEnum):
        BACK = 0
        BLANK = auto()
        MUTE = auto()
        UNMUTE = auto()
        PREVIOUS = auto()
        NEXT = auto()
        REWIND = auto()
        STOP = auto()
        PLAY = auto()
        PLAYING = auto()
        PAUSED = auto()
        FORWARD = auto()

    image_keys : list[str] = [
        "back.png", 
        "blank.png", 
        "mute-off.png", 
        "mute-on.png", 
        "previous.png",
        "next.png",
        "backward.png",
        "stop.png",
        "play.png",
        "playing.png",
        "paused.png", 
        "forward.png"
    ]

    def __init__(self, parent : IPlugin) -> None:
        super().__init__(parent)

        self._state : MediaControlsPlugin.State = MediaControlsPlugin.State.NONE
        self._now_playing : str = MediaControlsPlugin.NOTHING_PLAYING
        self._images : list[bytes] = None

    def activate(self) -> bool:
        super().activate()

        try:
            self._activated = True
            if self._images is None:
                self._images = []
                self._parent._load_images(self._images, MediaControlsPlugin.image_keys)

            self._parent._app.set_button_image(MediaControlsPlugin.Buttons.BACK, self._images[MediaControlsPlugin.ImageKeys.BACK])
            if self._parent.volume > 0:
                self._parent._app.set_button_image(MediaControlsPlugin.Buttons.MUTE, self._images[MediaControlsPlugin.ImageKeys.MUTE])
            else:
                self._parent._app.set_button_image(MediaControlsPlugin.Buttons.MUTE, self._images[MediaControlsPlugin.ImageKeys.UNMUTE])
            self._parent._app.set_button_image(MediaControlsPlugin.Buttons.PREVIOUS, self._images[MediaControlsPlugin.ImageKeys.PREVIOUS])
            self._parent._app.set_button_image(MediaControlsPlugin.Buttons.NEXT, self._images[MediaControlsPlugin.ImageKeys.NEXT])

            self._parent._app.set_button_image(MediaControlsPlugin.Buttons.REWIND, self._images[MediaControlsPlugin.ImageKeys.REWIND])
            self._parent._app.set_button_image(MediaControlsPlugin.Buttons.STOP, self._images[MediaControlsPlugin.ImageKeys.STOP])
            self._parent._app.set_button_image(MediaControlsPlugin.Buttons.PLAY, self._images[MediaControlsPlugin.ImageKeys.PLAY])
            self._parent._app.set_button_image(MediaControlsPlugin.Buttons.FORWARD, self._images[MediaControlsPlugin.ImageKeys.FORWARD])

            self._refresh_state()

        except Exception as ex:
            self._parent._log.error(f"Exception : {ex}")
            self._activated = False
        return self._activated

    def deactivate(self):
        super().deactivate()

    def on_button_press(self, key, key_state) -> bool:
        if not super().on_button_press(key, key_state): 
            return False
        match key:
            case MediaControlsPlugin.Buttons.BACK:
                return True
            case MediaControlsPlugin.Buttons.MUTE:
                self._parent.notify("Toggling Mute", False)
                self._parent.toggle_mute()
            case MediaControlsPlugin.Buttons.PREVIOUS:
                self._parent.notify("Jump Previous", False)
                self._parent.send_key(FireTvKeyCommands.PREVIOUS)
            case MediaControlsPlugin.Buttons.NEXT:
                self._parent.notify("Jump Next", False)
                self._parent.send_key(FireTvKeyCommands.NEXT)
            case MediaControlsPlugin.Buttons.REWIND:
                self._parent.notify("Rewinding", False)
                self._state = MediaControlsPlugin.State.REWINDING
                self._parent.send_key(FireTvKeyCommands.REWIND)
            case MediaControlsPlugin.Buttons.STOP:
                self._parent.notify("Stopping", False)
                self._state = MediaControlsPlugin.State.NONE
                self._parent.send_key(FireTvKeyCommands.STOP)
            case MediaControlsPlugin.Buttons.PLAY:
                match self._state:
                    case MediaControlsPlugin.State.PAUSED:
                        self._parent.notify("Playing", False)
                        self._state = MediaControlsPlugin.State.PLAYING
                        self._parent.send_key(FireTvKeyCommands.PLAY_PAUSE)
                    case MediaControlsPlugin.State.PLAYING:
                        self._parent.notify("Paused", False)
                        self._state = MediaControlsPlugin.State.PAUSED
                        self._parent.send_key(FireTvKeyCommands.PLAY_PAUSE)
                    case MediaControlsPlugin.State.NONE:
                        self._parent.notify("Playing", False)
                        self._state = MediaControlsPlugin.State.PLAYING
                        self._parent.send_key(FireTvKeyCommands.PLAY_PAUSE)
                    case _:
                        pass
            case MediaControlsPlugin.Buttons.FORWARD:
                self._parent.notify("Forwarding", False)
                self._state = MediaControlsPlugin.State.FORWARDING
                self._parent.send_key(FireTvKeyCommands.FAST_FORWARD)
            case _:
                pass
        self._refresh_state()
        return True

    def _refresh_state(self) -> None:
        try:

            cmd : str = "dumpsys media_session"
            result : str = self._parent.device.shell(cmd)
            if result is None:
                self._state = MediaControlsPlugin.State.NONE
                return

            result = result.split("Sessions Stack - ")[-1]
            lines : list[str] = result.splitlines()
            header : str = lines.pop(0).strip()
            h_parts = header.split(" ")
            num_sessions : int = 0
            for h in h_parts:
                if self._parent.is_integer(h):
                    num_sessions = int(h)
                    break
            if 0 == num_sessions:
                self._state = MediaControlsPlugin.State.NONE
                return

            now_playing : str = MediaControlsPlugin.NOTHING_PLAYING
            state : MediaControlsPlugin.State = MediaControlsPlugin.State.NONE

            for _ in range(0, num_sessions):
                line : str = lines.pop(0).strip()
                active : bool = True
                while (line):
                    if "=" in line:
                        parts : list[str] = line.split("=")
                        key : str = parts.pop(0).strip()
                        
                        if key == "active":
                            value : str = parts.pop(0).strip()
                            if value != "true":
                                active = False
                                break
                        elif key == "state":
                            value = "=".join(parts)
                            if value.startswith("PlaybackState "):
                                value = value.replace("PlaybackState ", "")
                                kvps = value.split(",")
                                for o in kvps:
                                    if not "=" in o: 
                                        continue
                                    kvp = o.split("=")
                                    key : str = kvp.pop(0).strip()
                                    
                                    if key == "{state":
                                        value : str = kvp.pop(0).strip()
                                        if not self._parent.is_integer(value):
                                            break
                                        value = int(value)
                                        match value:
                                            case 3:
                                                state = MediaControlsPlugin.State.PLAYING
                                            case 2:
                                                state = MediaControlsPlugin.State.PAUSED
                                            case 1:
                                                state = MediaControlsPlugin.State.NONE
                                            case _:
                                                state = MediaControlsPlugin.State.NONE
                                        if state != self._state:
                                            self._parent._log.debug(f"New state : {self._state}")
                        elif key == "metadata:size":
                            value = "=".join(parts)
                            kvps = value.split(",")
                            for o in kvps:
                                if not "=" in o: 
                                    continue
                                kvp = o.split("=")
                                key : str = kvp[0].strip()
                                value : str = kvp[1].strip()
                                if key == "description":
                                    if value != "null":
                                        if value != self._now_playing or state != self._state:
                                            self._parent._log.debug(f"Now playing : {value}")
                                            self._parent._log.debug("State : {state}")
                                            self._now_playing = value
                                            self._state = state
                                        return

                    line = lines.pop(0).strip()
                if not active: 
                    while line:
                        line = lines.pop(0).strip()

            self._now_playing = now_playing
            self._state = state
        except Exception as ex:
            self._parent._log.error(f"Exception : {ex}")
        return

    def _state_to_string(self, state : State):
        match state:
            case MediaControlsPlugin.State.NONE:
                return "None"
            case MediaControlsPlugin.State.PLAYING:
                return "Playing"
            case MediaControlsPlugin.State.PAUSED:
                return "Paused"
            case MediaControlsPlugin.State.REWINDING:
                return "Rewinding"
            case MediaControlsPlugin.State.FORWARDING:
                return "Forwarding"
            case _:
                return "Unknown"

    def on_dial_turned(self, dial, value) -> bool:
        if not super().on_dial_turned(dial, value): 
            return False
        return True

    def on_dial_pushed(self, dial, state) -> bool:
        if not super().on_dial_pushed(dial, state): 
            return False
        return True

    def status(self) -> str:
        self._refresh_state()
        result : str = f"Media : {self._now_playing} - ({self._state_to_string(self._state)})\n\n"
        result += self._parent.dials_info()
        return result

    def update_buttons(self) -> bool:
        if self._parent.volume > 0:
            self._parent._app.set_button_image(MediaControlsPlugin.Buttons.MUTE, self._images[MediaControlsPlugin.ImageKeys.MUTE])
        else:
            self._parent._app.set_button_image(MediaControlsPlugin.Buttons.MUTE, self._images[MediaControlsPlugin.ImageKeys.UNMUTE])

        match self._state:
            case MediaControlsPlugin.State.PLAYING:
                self._parent._app.set_button_image(MediaControlsPlugin.Buttons.PLAY, self._images[MediaControlsPlugin.ImageKeys.PLAYING])
            case MediaControlsPlugin.State.PAUSED:
                self._parent._app.set_button_image(MediaControlsPlugin.Buttons.PLAY, self._images[MediaControlsPlugin.ImageKeys.PAUSED])
            case _:
                self._parent._app.set_button_image(MediaControlsPlugin.Buttons.PLAY, self._images[MediaControlsPlugin.ImageKeys.PLAY])

class PackagesPlugin(IChildPlugin):

    class Buttons(IntEnum):
        BACK = 0

    class ImageKeys(IntEnum):
        BACK = 0
        BLANK = auto()

    image_keys : list[str] = [
        "back.png", 
        "blank.png"
    ]

    def __init__(self, parent : IPlugin) -> None:
        super().__init__(parent)

        self._images : list[bytes] = None
        self._packages : list[dict] = None
        self._package_counter : int = 0
        self._shortcuts : list[bytes] = None

    def activate(self) -> bool:
        super().activate()

        self._activated = True
        if self._images is None:
            self._images = []
            self._parent._load_images(self._images, PackagesPlugin.image_keys)

        self._parent._app.set_button_image(PackagesPlugin.Buttons.BACK, self._images[PackagesPlugin.ImageKeys.BACK])

        if self._shortcuts is None:
            s : list[str] = []
            for img in self._parent._config["packages"]:
                s.append(img["icon"])
            s = s[0:self._parent._app.num_buttons - 1]
            self._shortcuts = []
            self._parent._load_images(self._shortcuts, s)

        for i in range(1, len(self._shortcuts) + 1):
            self._parent._app.set_button_image(i, self._shortcuts[i - 1])

        for i in range(len(self._shortcuts) + 1, self._parent._app.num_buttons):
            self._parent._app.set_button_image(i, self._images[PackagesPlugin.ImageKeys.BLANK])

        if self._packages is None:
            self._packages = self._get_packages()
        self._parent._log.info(f"Loaded {len(self._packages)} packages")

        return self._activated

    def deactivate(self):
        super().deactivate()

    def on_button_press(self, key, key_state) -> bool:
        if not super().on_button_press(key, key_state): 
            return False
        match key:
            case PackagesPlugin.Buttons.BACK:
                pass
            case _:
                index : int = key - 1
                if index < len(self._shortcuts):
                    shortcut : dict = self._parent._config["packages"][index]
                    self._parent._log.info(f"Launching package: {shortcut['package']}")
                    self._parent.run_package(shortcut["package"])
        return True

    def on_dial_turned(self, dial, value) -> bool:
        if not super().on_dial_turned(dial, value): 
            return False
        match dial:
            case 0:
                self._package_counter = (self._package_counter + value) % len(self._packages)
            case _:
                pass
        return True

    def on_dial_pushed(self, dial, state) -> bool:
        if not super().on_dial_pushed(dial, state): 
            return False
        match dial:
            case 0:
                self._parent._log.info(f"Launching package: {self._packages[self._package_counter]['package']}")
                self._parent.run_package(self._packages[self._package_counter]["package"])
            case _:
                pass
        return True

    def status(self) -> str:
        result : str = f"Packages ({self._package_counter + 1}/{len(self._packages)}): \n  :-{self._packages[self._package_counter]['name']}\n"
        result += self._parent.dials_info()
        return result

    def update_buttons(self) -> bool:
        return super().update_buttons()

    def _get_packages(self) -> list[dict]:
        """
        Gets a sorted list of all 3rd party installed packages on the Fire TV system
        """
        results : list[dict] = []
        filtered : list[str] = self._parent.device.shell("pm list packages -3").splitlines()
        for f in filtered:
            parts = f.split(":")
            apk_name = parts[-1]
            friendly_name = "-".join(apk_name.split(".")[-2:])
            results.append({
                "name" : friendly_name,
                "package" : apk_name
            })
        return sorted(results, key = operator.itemgetter('name'))

class LiveTvPlugin(IChildPlugin):

    class Buttons(IntEnum):
        BACK = 0
        CHANNEL_UP = auto()
        MENU = auto()
        BLANK_1 = auto()

        BLANK_2 = auto()
        CHANNEL_DOWN = auto()
        HOME = auto()
        BLANK_3 = auto()

    class ImageKeys(IntEnum):
        BACK = 0
        HOME = auto()
        MENU = auto()
        CHANNEL_UP = auto()
        CHANNEL_DOWN = auto()
        BLANK = auto()

    image_keys : list[str] = [
        "back.png", 
        "home.png", 
        "menu.png", 
        "livetv-channel-up.png",
        "livetv-channel-down.png",
        "blank.png"
    ]

    def __init__(self, parent : IPlugin) -> None:
        super().__init__(parent)

        self._images : list[bytes] = None

    def activate(self) -> bool:
        super().activate()

        if self._images is None:
            self._images = []
            self._parent._load_images(self._images, LiveTvPlugin.image_keys)

        self._parent._app.set_button_image(LiveTvPlugin.Buttons.BACK, self._images[LiveTvPlugin.ImageKeys.BACK])
        self._parent._app.set_button_image(LiveTvPlugin.Buttons.CHANNEL_UP, self._images[LiveTvPlugin.ImageKeys.CHANNEL_UP])
        self._parent._app.set_button_image(LiveTvPlugin.Buttons.MENU, self._images[LiveTvPlugin.ImageKeys.MENU])
        self._parent._app.set_button_image(LiveTvPlugin.Buttons.BLANK_1, self._images[LiveTvPlugin.ImageKeys.BLANK])
        self._parent._app.set_button_image(LiveTvPlugin.Buttons.HOME, self._images[LiveTvPlugin.ImageKeys.HOME])
        self._parent._app.set_button_image(LiveTvPlugin.Buttons.CHANNEL_DOWN, self._images[LiveTvPlugin.ImageKeys.CHANNEL_DOWN])
        self._parent._app.set_button_image(LiveTvPlugin.Buttons.BLANK_2, self._images[LiveTvPlugin.ImageKeys.BLANK])
        self._parent._app.set_button_image(LiveTvPlugin.Buttons.BLANK_3, self._images[LiveTvPlugin.ImageKeys.BLANK])

        # activate tv mode
        self._parent.send_key(FireTvKeyCommands.TV_INPUT)
        self._activated = True

        return self._activated

    def deactivate(self):
        super().deactivate()

    def on_button_press(self, key, key_state) -> bool:
        if not super().on_button_press(key, key_state): 
            return False
        match key:
            case LiveTvPlugin.Buttons.BACK:
                self._parent._app._log.error("We should handle this upstream!")
            case LiveTvPlugin.Buttons.CHANNEL_UP:
                self._parent.send_key(FireTvKeyCommands.TV_CHANNEL_UP)
            case LiveTvPlugin.Buttons.MENU:
                self._parent.send_key(FireTvKeyCommands.MENU)
            case LiveTvPlugin.Buttons.HOME:
                self._parent.send_key(FireTvKeyCommands.HOME)
            case LiveTvPlugin.Buttons.CHANNEL_DOWN:
                self._parent.send_key(FireTvKeyCommands.TV_CHANNEL_DOWN)
            case _:
                pass

    def on_dial_turned(self, dial, value) -> bool:
        if not super().on_dial_turned(dial, value): 
            return False

    def on_dial_pushed(self, dial, state) -> bool:
        if not super().on_dial_pushed(dial, state): 
            return False

    def status(self) -> str:
        result : str = "Live TV\n\n"
        result += self._parent.dials_info()
        return result
    
    def update_buttons(self) -> bool:
        return super().update_buttons()