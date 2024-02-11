from enum import Enum
from ..IPlugin import IPlugin
from PyTado import interface

import textwrap

# https://blog.scphillips.com/posts/2017/01/the-tado-api-v2/

class TadoPlugin(IPlugin):

    class Buttons(Enum):
        BACK = 0
        ZONES = 1
        DEVICES = 2
        ON = 3
        HOME = 4
        WEATHER = 5
        ANALYTICS = 6
        OFF = 7

    class State(Enum):
        NONE = 0
        ZONES = 1
        ZONE_INFO = 2
        DEVICES = 3
        ON = 4
        HOME = 5
        WEATHER = 6
        ANALYTICS = 7
        OFF = 8

    image_keys = [ "zones.png", "devices.png", "on.png", "home.png", "weather.png", "analytics.png", "off.png" ]

    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)
        self._state = TadoPlugin.State.NONE
        self._zones = []
        self._zone_info = None
        self._devices = []
        self._zone_index = 0
        self._device_index = 0
        self._tado = None
        self._images = None

    def activate(self) -> bool:
        if (not super().activate()): return False

        try:
            if (None == self._tado):
                if (not self._config["username"] or not self._config["password"]):
                    self._log.error("Credentials are required")
                    return False
                self._tado = interface.Tado(self._config["username"], self._config["password"])

            self._activated = True
            self._reset_state()
            self._show_default()
        except Exception as ex:
            self._log.error(ex)
            self._activated = False
        return self._activated

    def run_as_daemon(self) -> None:
        pass

    def on_button_press(self, deck, key, key_state):
        super().on_button_press(deck, key, key_state)

        if (not key_state): return
        match key:
            case TadoPlugin.Buttons.BACK.value:
                pass
            case TadoPlugin.Buttons.ZONES.value:
                self._reset_state()
                self._state = TadoPlugin.State.ZONES
                self._show_zones()
            case TadoPlugin.Buttons.DEVICES.value:
                self._reset_state()
                self._state = TadoPlugin.State.DEVICES
                self._show_devices()
            case TadoPlugin.Buttons.WEATHER.value:
                self._reset_state()
                self._state = TadoPlugin.State.WEATHER
                self._show_weather()
            case TadoPlugin.Buttons.HOME.value:
                self._reset_state()
                self._state = TadoPlugin.State.HOME
                self._home_state = self._tado.get_home_state()["presence"]
                self._show_home()

    def on_dial_turned(self, deck, dial, value):
        super().on_dial_turned(deck, dial, value)

        match self._state:
            case TadoPlugin.State.ZONES:
                if (dial == 0):
                    self._zone_info = None
                    self._zone_index += sorted((-1, value, 1))[1]
                    self._zone_index = self._wrap(self._zone_index, len(self._zones))
                    self._show_zones()
            case TadoPlugin.State.ZONE_INFO:
                if (dial == 0):
                    self._state = TadoPlugin.State.ZONES
                    self.on_dial_turned(deck, dial, value)
                elif (dial == 1):
                    # temperature
                    if (value > 0):
                        self._zone_info["target"] += 0.5
                    else:
                        self._zone_info["target"] -= 0.5
                    self._show_zone_info()
            case TadoPlugin.State.DEVICES:
                if (dial != 0):
                    return
                self._device_index += sorted((-1, value, 1))[1]
                self._device_index = self._wrap(self._device_index, len(self._devices))
                self._show_devices()
            case TadoPlugin.State.HOME:
                if (dial != 0):
                    return
                if (self._home_state == "HOME"):
                    self._home_state = "AWAY"
                else:
                    self._home_state = "HOME"
                self._show_home()

    def on_dial_pushed(self, deck, dial, value):
        super().on_dial_pushed(deck, dial, value)

        if not value: return
        match self._state:
            case TadoPlugin.State.ZONES:
                if (dial != 0):
                    return
                zi = self._tado.get_zone_state(self._zones[self._zone_index]["id"])
                self._zone_info = {
                    "target": zi.target_temp, 
                    "info": zi
                }
                self._show_zone_info()
            case TadoPlugin.State.ZONE_INFO:
                if (dial == 1):
                    # write the new target temp, until next scheduled change
                    target = str(self._zone_info["target"])
                    self._render("Storing new target : " + target, 33)
                    self._tado.set_zone_overlay(self._zones[self._zone_index]["id"], "TADO_MODE", set_temp = target)
                    self._show_zone_info()
            case TadoPlugin.State.DEVICES:
                self._show_device_info(self._devices[self._device_index])
            case TadoPlugin.State.HOME:
                self._render("Storing home state", 33)
                if (self._home_state == "HOME"):
                    self._tado.set_home()
                else:
                    self._tado.set_away()
                self._show_home()

    def _reset_state(self):
        self._state = TadoPlugin.State.NONE
        self._home_state = "HOME"
        self._zone_index = 0
        self._device_index = 0

    def _show_default(self):
        if (self._images == None):
            self._images = []
            self._load_images(self._images, TadoPlugin.image_keys)
        for n in range (0,  len(TadoPlugin.Buttons) - 1):
            self._app.set_button_image(n + 1, self._images[n])
        self._render(self._name)

    def _show_zones(self):
        if (0 == len(self._zones)):
            self._render("Loading zones", 50)
            self._zones = self._tado.get_zones()
        current_zone = self._zones[self._zone_index]
        self._render("Zone : " + current_zone["name"], 50)

    def _show_zone_info(self):
        self._state = TadoPlugin.State.ZONE_INFO
        name : str = self._zones[self._zone_index]["name"]
        temp : str = str(int(self._zone_info["info"].current_temp))
        target : str = str(int(self._zone_info["target"]))
        humidity : str = str(int(self._zone_info["info"].current_humidity))
        info : str = textwrap.dedent(f"""\
            {name} (is {temp} degrees)
            Target is {target} degrees
            Humidity at {humidity} %"""
        )
        self._render(info)

    def _show_device_info(self, device):
        connected = "Connected" if device["connectionState"]["value"] else "Disconnected"
        match device["deviceType"]:
            case "IB01":
                msg : str = textwrap.dedent(f"""\
                    Base Station: {device['shortSerialNo']}
                    {connected}
                    Firmware: {device['currentFwVersion']}"""                  
                )
            case "SU02":
                msg : str = textwrap.dedent(f"""\
                    Thermostat: {device['shortSerialNo']}
                    {connected}, Battery state: {device['batteryState']}
                    {device['characteristics']['capabilities']}"""                  
                )
            case "VA02":
                msg : str = textwrap.dedent(f"""\
                    Valve : {device['shortSerialNo']}
                    {connected}, Battery state: {device['batteryState']}
                    Mounted: {device['orientation']} - [{device['mountingState']['value']}]"""                  
                )
            case _:
                msg : str = textwrap.dedent(f"""\
                    Unknown Device : {device['shortSerialNo']}
                    {connected}, Battery state: {device['batteryState']}
                    {device['characteristics']['capabilities']}"""                  
                )
        self._render(msg)
        pass

    def _show_devices(self):
        if (0 == len(self._devices)):
            self._render("Loading devices", 50)
            self._devices = self._tado.get_devices()
        current_device = self._devices[self._device_index]
        self._render("Device : " + current_device["serialNo"], 50)

    def _show_weather(self):
        weather = self._tado.get_weather()
        msg : str = textwrap.dedent(f"""\
            Currently it is {weather['weatherState']['value']}
            The temp is {int(weather['outsideTemperature']['celsius'])} degrees
            Solar intensity at {int(weather['solarIntensity']['percentage'])} %"""
        )
        self._render(msg)

    def _show_home(self):
        self._render(self._home_state, 33)

    def deactivate(self):
        super().deactivate()
        self._zones.clear()
        self._devices.clear()

    def destroy(self):
        super().destroy()
