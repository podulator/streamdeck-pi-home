from ..IPlugin import IPlugin
from .shared import IChildPlugin, MediaControlsPlugin, LiveTvPlugin, PackagesPlugin
from .shared import FireTvKeyCommands

from adb_shell.adb_device import AdbDeviceTcp
from adb_shell.auth.sign_pythonrsa import PythonRSASigner
from adb_shell.auth.keygen import keygen
from enum import IntEnum, auto

import os
import threading
import time

class FireTvPlugin(IPlugin):

    class ActiveMode(IntEnum):
        HOME = 0
        MEDIA = auto()
        LIVE_TV = auto()
        PACKAGES = auto()

    class WakeState(IntEnum):
        NONE = 0
        ASLEEP = auto()
        DREAMING = auto()
        AWAKE = auto()

    class Buttons(IntEnum):
        EXIT = 0
        MEDIA = auto()
        TV = auto()
        SHORTCUT = auto()
        PACKAGES = auto()
        POWER = auto()
        ALEXA = auto()
        HOME = auto()

    class ImageKeys(IntEnum):
        MEDIA = 0
        TV = auto()
        SHORTCUT = auto()
        PACKAGES = auto()
        POWER_OFF = auto()
        POWER_ON = auto()
        ALEXA = auto()
        HOME = auto()

    KEY_NAME : str = "adbkey"

    image_keys :list[str] = [ 
        "media.png", 
        "tv.png", 
        "shortcut.png", 
        "packages.png", 
        "off.png", 
        "on.png", 
        "alexa.png", 
        "home.png" 
    ]

    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)

        self._device : AdbDeviceTcp = None
        self._images : list[bytes] = None
        self._active_mode : FireTvPlugin.ActiveMode = FireTvPlugin.ActiveMode.HOME
        self._plugins : list[IChildPlugin] = None
        self._wake_state : FireTvPlugin.WakeState = FireTvPlugin.WakeState.NONE
        self._device_screen_on : bool = False
        self._creds : PythonRSASigner = None
        self._volume : int = 0
        self._last_volume : int = -1
        self._volume_min : int = 0
        self._volume_max : int = 0
        self._thread : threading.Thread = None

        self._help_message = "Fire TV plugin\nBack | Media | Live TV | Switch Input\nApps | Power | Alexa | Home"

    @property
    def device(self) -> AdbDeviceTcp:
        return self._device

    @property
    def volume(self) -> int:
        return self._volume

    def activate(self) -> bool:
        try:
            if not super().activate(): 
                return False
            self._activated = True

            if None == self._images:
                self._images = []
                self._load_images(self._images, FireTvPlugin.image_keys)

            if self._plugins is None:
                self._plugins = [
                    MediaControlsPlugin(self),
                    LiveTvPlugin(self), 
                    PackagesPlugin(self)
                ]

            if self._creds is None:
                self._creds = self._get_creds()

            if self._device is None:
                ip : str = self._config["ip_address"]
                port : int = self._config["port"]
                self._log.debug(f"Connecting to {ip}:{port}")
                self._device : AdbDeviceTcp = AdbDeviceTcp(
                    host = ip, 
                    port = port, 
                    default_transport_timeout_s = 9.0
                )

            self._device.connect(rsa_keys = [self._creds], auth_timeout_s = 10.0)
            
            self._refresh_volume()

            if self._thread is None:
                self._thread = threading.Thread(target=self._thread_loop)
                self._thread.start()

        except Exception as ex:
            self._activated = False
            self._log.error(ex)

        return self._activated

    def _thread_loop(self):
        self._log.debug("Starting thread loop")
        counter : int = 0
        while (self._activated):
            try:
                counter += 1
                if counter > 15:
                    counter = 0
                    self._refresh_wake_state()
                    self._update_display()
                    self._update_buttons()
            except:
                pass
            time.sleep(1.0)
        self._log.debug("Exiting thread loop")

    def deactivate(self):
        super().deactivate()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        if self._device is not None:
            self._device.close()
            self._device = None

    def destroy(self):
        super().destroy()
        self.deactivate()
        self._device = None

    def run_as_daemon(self) -> None:
        pass

    def handle_back_button(self) -> bool:
        if self._active_mode != FireTvPlugin.ActiveMode.HOME:
            self._log.debug("Returning to plugin home")
            self._active_mode = FireTvPlugin.ActiveMode.HOME
            self._refresh_wake_state()
            self._update_display()
            self._update_buttons()
            return True
        return False

    def notify(self, message : str, keep : bool = False):
        self._render(message)
        if not keep:
            timer = threading.Timer(5.0, self._update_display)
            timer.start()

    def dials_info(self) -> str:
        result : str = "Rotate            Vol.              D / U             L / R\n"
        result += "Push              Home             Back          Select"
        return result

    def on_button_press(self, deck, key, key_state):
        super().on_button_press(deck, key, key_state)
        if not key_state: 
            return

        match self._active_mode:
            case FireTvPlugin.ActiveMode.HOME:
                match key:
                    case FireTvPlugin.Buttons.EXIT:
                        self._log.error("We have hit a back call")
                    case FireTvPlugin.Buttons.MEDIA:
                        self._active_mode = FireTvPlugin.ActiveMode.MEDIA
                        self._plugins[self._active_mode - 1].activate()
                    case FireTvPlugin.Buttons.TV:
                        self._active_mode = FireTvPlugin.ActiveMode.LIVE_TV
                        self._plugins[self._active_mode - 1].activate()
                    case FireTvPlugin.Buttons.SHORTCUT:
                        self.send_key(FireTvKeyCommands.SHORTCUT_1)
                    case FireTvPlugin.Buttons.PACKAGES:
                        self._active_mode = FireTvPlugin.ActiveMode.PACKAGES
                        self._plugins[self._active_mode - 1].activate()
                    case FireTvPlugin.Buttons.POWER:
                        match self._wake_state:
                            case FireTvPlugin.WakeState.AWAKE:
                                self.send_key(FireTvKeyCommands.SLEEP)
                            case _:
                                self.send_key(FireTvKeyCommands.WAKE_UP)
                    case FireTvPlugin.Buttons.ALEXA:
                        self.send_key(FireTvKeyCommands.ACTIVATE_ALEXA)
                    case FireTvPlugin.Buttons.HOME:
                        self.send_key(FireTvKeyCommands.HOME)
                    case _:
                        self.debug(f"Unknown button : {key}")
            case _:
                self._plugins[self._active_mode - 1].on_button_press(key, key_state)

        self._refresh_wake_state()
        self._refresh_volume()
        self._update_display()
        self._update_buttons()

    def on_dial_pushed(self, deck, dial, state):
        super().on_dial_pushed(deck, dial, state)
        if not state: 
            return

        match dial:
            case 0:
                match self._active_mode:
                    case FireTvPlugin.ActiveMode.HOME:
                        pass
                    case _:
                        if self._active_mode <= len(self._plugins):
                            self._plugins[self._active_mode - 1].on_dial_pushed(dial, state)
            case 1:
                self.send_key(FireTvKeyCommands.HOME)
            case 2:
                self.send_key(FireTvKeyCommands.BACK)
            case 3:
                self.send_key(FireTvKeyCommands.SELECT)

    def on_dial_turned(self, deck, dial, value):
        super().on_dial_turned(deck, dial, value)

        match dial:
            case 0:
                match self._active_mode:
                    case FireTvPlugin.ActiveMode.HOME:
                        pass
                    case _:
                        if self._active_mode <= len(self._plugins):
                            self._plugins[self._active_mode - 1].on_dial_turned(dial, value)
            case 1:
                self._adjust_volume(value)
            case 2:
                if value < 0:
                    self.send_key(FireTvKeyCommands.DPAD_DOWN)
                else:
                    self.send_key(FireTvKeyCommands.DPAD_UP)
            case 3:
                if value < 0:
                    self.send_key(FireTvKeyCommands.DPAD_LEFT)
                else:
                    self.send_key(FireTvKeyCommands.DPAD_RIGHT)
        
        self._update_display()

    def _update_display(self) -> None:

        msg : str = None
        match self._active_mode:
            case FireTvPlugin.ActiveMode.HOME:
                state : str = "Connected" if self._device.available else "Disconnected"
                msg = f"{self._name} state : {state}\n\n{self.dials_info()}"
            case FireTvPlugin.ActiveMode.MEDIA:
                msg = self._plugins[self._active_mode - 1].status()
            case FireTvPlugin.ActiveMode.LIVE_TV:
                msg = self._plugins[self._active_mode - 1].status()
            case FireTvPlugin.ActiveMode.PACKAGES:
                msg = self._plugins[self._active_mode - 1].status()
            case _:
                msg = f"Unknown active state : {self._active_mode}"

        self._render(msg)

    def _update_buttons(self) -> None:

        match self._active_mode:
            case FireTvPlugin.ActiveMode.HOME:

                # these guys don't change much
                self._app.set_button_image(FireTvPlugin.Buttons.EXIT, self._app.home_image)
                self._app.set_button_image(FireTvPlugin.Buttons.MEDIA, self._images[FireTvPlugin.ImageKeys.MEDIA])
                self._app.set_button_image(FireTvPlugin.Buttons.TV, self._images[FireTvPlugin.ImageKeys.TV])
                self._app.set_button_image(FireTvPlugin.Buttons.SHORTCUT, self._images[FireTvPlugin.ImageKeys.SHORTCUT])
                self._app.set_button_image(FireTvPlugin.Buttons.PACKAGES, self._images[FireTvPlugin.ImageKeys.PACKAGES])
                if self._wake_state == FireTvPlugin.WakeState.AWAKE or self._wake_state == FireTvPlugin.WakeState.DREAMING:
                    self._app.set_button_image(FireTvPlugin.Buttons.POWER, self._images[FireTvPlugin.ImageKeys.POWER_ON])
                else:
                    self._app.set_button_image(FireTvPlugin.Buttons.POWER, self._images[FireTvPlugin.ImageKeys.POWER_OFF])
                self._app.set_button_image(FireTvPlugin.Buttons.ALEXA, self._images[FireTvPlugin.ImageKeys.ALEXA])
                self._app.set_button_image(FireTvPlugin.Buttons.HOME, self._images[FireTvPlugin.ImageKeys.HOME])

            case FireTvPlugin.ActiveMode.MEDIA:
                self._plugins[self._active_mode - 1].update_buttons()
            case FireTvPlugin.ActiveMode.LIVE_TV:
                self._plugins[self._active_mode - 1].update_buttons()
            case FireTvPlugin.ActiveMode.PACKAGES:
                self._plugins[self._active_mode - 1].update_buttons()
            case _:
                self._log.debug(f"Unknown active mode : {self._active_mode}")
                return
    
    def _refresh_wake_state(self) -> None:

        try:
            cmd : str = 'dumpsys power | grep -e "mWakefulness=" -e "Display Power"'
            results : list[str] = self._device.shell(cmd).splitlines()

            if len(results) != 2:
                self._log.error(f"Invalid results : {results}")
                return

            result : str = results[0].split("=")[1].strip().lower()
            match result:
                case "awake":
                    self._wake_state = FireTvPlugin.WakeState.AWAKE
                case "asleep":
                    self._wake_state = FireTvPlugin.WakeState.ASLEEP
                case "dreaming":
                    self._wake_state = FireTvPlugin.WakeState.DREAMING
                case _:
                    self._wake_state = FireTvPlugin.WakeState.NONE
                    self._log.error(f"Invalid wake state : {result}")

            result = results[1].split("=")[1].strip().lower()
            match result:
                case "on":
                    self._device_screen_on = True
                case "off":
                    self._device_screen_on = False
                case _:
                    self._device_screen_on = False
                    self._log.error(f"Invalid screen state : {result}")

        except Exception as ex:
            self._log.error(ex)

    def _adjust_volume(self, value : int = 0) -> bool:
        try:
            new_volume : int = max(min(self._volume_max, (self._volume + value)), self._volume_min)
            if new_volume != self._volume:
                self._log.debug(f"Setting new volume to : {new_volume}")
                cmd : str = f"media volume --stream 3 --set {new_volume}"
                self._device.shell(cmd)
                self._refresh_volume()
            return self._volume == new_volume
        except Exception as ex:
            self._log.error(ex)
            return False

    def _refresh_volume(self) -> None:
        try:
            #cmd : str = 'dumpsys audio | grep -e "mMasterVolume=" -e "mMasterMute"'
            cmd : str = "media volume --stream 3 --get | grep range"
            results : list[str] = self._device.shell(cmd).splitlines()
            if len(results) != 1 :
                self._log.error(f"Invalid results : {results}")
                return

            parts : list[str] = results[0].split(".")
            for p in parts[0].split(" "):
                if self.is_integer(p):
                    new_volume : int = int(p)
                    if self._volume != new_volume:
                        self._log.debug(f"New volume : {new_volume}")
                        self._volume = new_volume
                    break

            if self._volume_min == self._volume_max:
                part : str = parts[-1].replace("]", "").strip()
                if self.is_integer(part):
                    self._volume_max = int(part)

        except Exception as ex:
            self._log.error(ex)

    def _get_creds(self) -> PythonRSASigner:
        try:
            key_name : str = self._config.get("key_file_name", FireTvPlugin.KEY_NAME)
            key_base_path : str = os.path.join(self._app.creds_path, key_name)
            if not os.path.isfile(key_base_path):
                self._log.info(f"Generating new adb key : {key_base_path}")
                keygen(key_base_path)

            with open(key_base_path, 'r') as f:
                private_key = f.read()
            with open(key_base_path + ".pub", 'r') as f:
                public_key = f.read()

            return PythonRSASigner(public_key, private_key)

        except Exception as ex:
            self._log.error(ex)
            return None

    def is_integer(self, n) -> bool:
        try:
            float(n)
        except ValueError:
            return False
        else:
            return float(n).is_integer

    def send_key(self, key : FireTvKeyCommands) -> None:
        self._log.debug(f"Sending key command : {key}")
        self._device.shell(f"input keyevent {key}")

    def run_package(self, package : str) -> None:
        self._log.debug(f"Running package : {package}")
        self._device.shell(f"monkey -p {package} 1")

    def toggle_mute(self) -> None:
        if self._volume > 0:
            self._log.debug(f"Muting from : {self._volume}")
            self._last_volume = self._volume
            self._device.shell("media volume --stream 3 --set 0")
        else:
            self._log.debug(f"Un-muting to : {self._last_volume}")
            value :int = self._last_volume
            self._device.shell(f"media volume --stream 3 --set {value}")

        self._refresh_volume()
