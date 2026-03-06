from enum import Enum
from ..IPlugin import IPlugin
from .VacuumDevice import VacuumDevice

class VacuumPlugin(IPlugin):

    class Buttons(Enum):
        BACK = 0
        CLEAN = 1
        CHARGE = 2
        STATUS = 3

    class State(Enum):
        NONE = 0
        CLEANING = 1
        PAUSED = 2
        CHARGING = 3

    image_keys = [ "zones.png", "devices.png", "on.png", "home.png", "weather.png", "analytics.png", "off.png" ]

    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)
        self._device : VacuumDevice = None
        self._state : VacuumPlugin.State = VacuumPlugin.State.NONE

    def run_as_daemon(self) -> None:
        pass

    def on_button_press(self, deck, key, key_state):
        super().on_button_press(deck, key, key_state)

        if (not key_state): return

    def on_dial_turned(self, deck, dial, value):
        super().on_dial_turned(deck, dial, value)

    def on_dial_pushed(self, deck, dial, value):
        super().on_dial_pushed(deck, dial, value)

        if not value: return

    def _show_home(self):
        self._render(self._name, 33)

    def deactivate(self):
        super().deactivate()

    def destroy(self):
        super().destroy()
