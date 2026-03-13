import threading
import time

from enum import auto, IntEnum
from ..IPlugin import IPlugin
from .VacuumDevice import VacuumDevice

class VacuumPlugin(IPlugin):

    class Buttons(IntEnum):
        BACK = 0
        CLEAN = auto()
        CHARGE = auto()
        STATUS = auto()

    class State(IntEnum):
        NONE = 0
        CLEANING = auto()
        PAUSED = auto()
        CHARGING = auto()

    class ImageKeys(IntEnum):
        CLEAN = 0
        PAUSE = auto()
        CHARGE = auto()
        BLANK = auto()

    image_keys = [ "clean.png", "pause.png", "charge.png", "blank.png"]

    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)
        self._device : VacuumDevice = None
        self._state : VacuumPlugin.State = VacuumPlugin.State.NONE
        self._images = None
        self._status_counter: int = 0
        self._thread : thread = None
        self._running: bool = False
        self._help_message = "Tuya Vacuum plugin\nBack | Clean | Charge"

    def activate(self) -> bool:
        if (not super().activate()): return False

        self._state = VacuumPlugin.State.NONE
        self._status_counter = 0
    
        try:
            if (None == self._device):
                if not self._config["local_key"]:
                    self._log.error("Credentials are required")
                    return False
                self._render("Connecting...", 50)

                self._device = VacuumDevice(
                    dev_id=self._config["device_id"],
                    address=self._config["ip_address"],
                    local_key=self._config["local_key"],
                    version = self._config["protocol_version"]
                )

            if self._thread is None:
                self._running = True
                self._thread = threading.Thread(target = self._run)
                self._thread.start()
                    
            self._activated = True
            self._show_default()

        except Exception as ex:
            self._device = None
            self._log.error(ex)
            self._activated = False

        return self._activated

    def run_as_daemon(self) -> None:
        pass

    def on_button_press(self, deck, key, key_state):
        super().on_button_press(deck, key, key_state)

        if (not key_state): return
        match key:
            case VacuumPlugin.Buttons.BACK.value:
                return
            case VacuumPlugin.Buttons.CLEAN.value:
                match self._state:
                    case VacuumPlugin.State.CLEANING:
                        self._device.pause()
                        self._state = VacuumPlugin.State.PAUSED
                    case VacuumPlugin.State.PAUSED:
                        self._device.clean()
                        self._state = VacuumPlugin.State.CLEANING
                    case _:
                        self._device.clean()
                        self._state = VacuumPlugin.State.CLEANING
            case VacuumPlugin.Buttons.CHARGE.value:
                if self._state == VacuumPlugin.State.CHARGING:
                    return
                self._device.charge()
                self._state = VacuumPlugin.State.CHARGING

        self._update_buttons()

    def _show_home(self):
        self._render(self._name, 33)

    def deactivate(self):
        try:
            self._running = False
            if self._thread is not None:
                self._thread.join()
                self._thread = None
        except:
            pass
        super().deactivate()

    def destroy(self):
        super().destroy()

    def _update_buttons(self) -> None:
        if not self._activated: return
        try:

            if self._images is None:
                self._images = []
                self._load_images(self._images, VacuumPlugin.image_keys)

            match self._state:
                case VacuumPlugin.State.CLEANING:
                    self._app.set_button_image(VacuumPlugin.Buttons.CHARGE, self._images[VacuumPlugin.ImageKeys.CHARGE])
                    self._app.set_button_image(VacuumPlugin.Buttons.CLEAN.value, self._images[VacuumPlugin.ImageKeys.PAUSE])
                case VacuumPlugin.State.PAUSED:
                    self._app.set_button_image(VacuumPlugin.Buttons.CHARGE, self._images[VacuumPlugin.ImageKeys.CHARGE])
                    self._app.set_button_image(VacuumPlugin.Buttons.CLEAN.value, self._images[VacuumPlugin.ImageKeys.CLEAN])
                case _:
                    self._app.set_button_image(VacuumPlugin.Buttons.CHARGE, self._images[VacuumPlugin.ImageKeys.BLANK])
                    self._app.set_button_image(VacuumPlugin.Buttons.CLEAN.value, self._images[VacuumPlugin.ImageKeys.CLEAN])

        except Exception as ex:
            self._log.error(ex)

    def _update_status(self):
        if not self._activated: return

        try:
            status: dict = self._device.status()
            #self._log.debug(str(status))

            match self._state:
                case VacuumPlugin.State.CHARGING:
                    charge: str = status["ELECTRICITY_LEFT"]
                    self._render(f"{self._name}\nCharging: {charge}%")
                case _:
                    status_keys = ["POWER", "MODE", "STATUS", "ELECTRICITY_LEFT", "CLEAN_TIME"]
                    self._status_counter = (self._status_counter + 1) % len(status_keys)
                    key: str = status_keys[self._status_counter]
                    nice_key : str = key.capitalize().replace("_", " ")
                    value : str = status[key]
                    self._render(f"{self._name}\n{nice_key} = {value}")

        except Exception as ex:
            self._log.error(ex)

    def _show_default(self):
        self._update_buttons()
        self._render(self._name)

    ### thread entry point for just lopping thru our status
    def _run(self) -> None:
        if not self._activated: return
    
        self._log.info(f"{self._class} thread starting")
        while (self._running):
            time.sleep(10)
            self._update_status()
        self._log.info(f"{self._class} thread exiting")
