from ..IPlugin import IPlugin
from .accessory import IAccessory, AccessoryFactory
from .characteristic import ICharacteristic
from .shared import *
from .zone import VeluxZone
from enum import Enum
from homekit.controller.ip_implementation import IpPairing

import homekit
import os
import threading
import time

class VeluxPlugin(IPlugin):

    REFRESH_INTERVAL : int = 60

    image_keys : list[str] = [ 
        "gateway.png", 
        "sensor.png",
	    "zones.png", 
        "shutter.png", 
        "window.png", 
        "blank.png"
    ]

    class State(Enum):
        NONE = 0
        GATEWAY = 1
        SENSOR = 2
        SENSOR_DETAILS = 3
        ZONES = 4
        ZONE_ACCESSORY_SELECT = 5
        ZONE_ACCESSORY_SHOW = 6
        SHUTTERS = 7
        SHUTTER_ACCESSORIES = 8
        WINDOWS = 9
        WINDOW_ACCESSORIES = 10

    class Buttons(Enum):
        BACK = 0
        GATEWAY = 1
        SENSOR = 2
        ZONES = 3
        SHUTTERS = 4
        WINDOWS = 5

    class Images(Enum):
        GATEWAY = 0
        SENSOR = 1
        ZONES = 2
        SHUTTER = 3
        WINDOW = 4
        BLANK = 5

    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)
        self._accessories : list[:IAccessory] = []
        self._zones : list[:VeluxZone] = []
        self._types : list[:VeluxTypes] = []
        self._images : list[bytes] = None
        self._state : VeluxPlugin.State = VeluxPlugin.State.NONE
        self._ctrl : homekit.Controller = None
        self._thread : threading.Thread = None
        self._thread_counter : int = 0
        self._sensor_counter : int = 0
        self._zone_counter : int = 0
        self._za_counter : int = 0
        self._shutter_counter : int = 0
        self._window_counter : int = 0
        self._help_message = "Velux plugin\nBack | Info | Sensors | Zones\nBlinds | Windows | N/A | N/A"

    def activate(self) -> bool:
        if not super().activate(): 
            return False

        try:
            self._activated = True
            if None == self._images:
                self._images = []
                self._load_images(self._images, VeluxPlugin.image_keys)

            if len(self._accessories) == 0:
                try:
                    if self._ctrl is None:
                        homekit_file : str = self._config.get("homekit_file", None)
                        homekit_file_path = os.path.join(self._app.creds_path, homekit_file)
                        if not os.path.isfile(homekit_file_path):
                            self._log.error(f"Homekit file not found : {homekit_file_path}")
                            self._activated = False
                            return self._activated
                        self._ctrl = homekit.Controller()
                        self._ctrl.load_data(homekit_file_path)

                    self._poll_environment()
                    self._log.info(f"Loaded {len(self._zones)} zones")
                    self._log.info(f"Loaded {len(self._accessories)} accessories")
                    self._log.info(f"Loaded {len(self._types)} types")
                    self._activated = (
                        len(self._zones) > 0 and 
                        len(self._accessories) > 0 and 
                        len(self._types) > 0
                    )
                except Exception as ex:
                    self._log.error(f"Couldn't load accessories : {ex}")
                    self._activated = False

            if self._activated:
                self._initialize()
                self._update_buttons()
                self._update_screen()

            if self._thread is None:
                self._thread = threading.Thread(target = self._thread_loop)
                self._thread.start()

        except Exception as ex:
            self._log.error(ex)
            self._activated = False
        return self._activated

    def _thread_loop(self):
        if self._thread is None: 
            return
        try:
            counter : int = 0
            self._log.info("Thread is starting")
            while (self._activated):
                counter += 1
                if counter > VeluxPlugin.REFRESH_INTERVAL:
                    counter = 0
                    if not self._poll_environment():
                        counter = VeluxPlugin.REFRESH_INTERVAL - 5
                    else:
                        self._update_screen()
                time.sleep(1)

        except Exception as ex:
            self._log.error("Thread exception : {ex}")
        self._log.info("Thread exiting")

    def _poll_environment(self) -> bool:

        try:
            pairing : IpPairing = self._ctrl.get_pairings()[self._config["homekit_alias"]]
            data = pairing.list_accessories_and_characteristics()

            # temp holders for atomic switch
            accessories : list[IAccessory] = []
            zones : list[VeluxZone] = []
            types : list[VeluxTypes] = []

            # arranged by zone
            for zone in self._config["zones"]:
                z = VeluxZone(zone["name"])
                zones.append(z)
                for key in zone["accessories"]:
                    id : int = key["id"]
                    name : str = key["name"]
                    for d in data:
                        if (d["aid"] == id):
                            accessory : IAccessory = AccessoryFactory.new(name, d, pairing)
                            if (accessory):
                                accessories.append(accessory)
                                z.accessories.append(accessory)
                                if (not types.__contains__(accessory.type)):
                                    types.append(accessory.type)
                            break
            # switch
            self._types = types
            self._zones = zones
            self._accessories = accessories
            return True

        except:
            # polling can timeout on the gateway, we just pick it up next time
           return False

    def deactivate(self):
        super().deactivate()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def destroy(self):
        super().destroy()

    def run_as_daemon(self) -> None:
        pass

    def on_dial_turned(self, deck, dial, value):
        super().on_dial_turned(deck, dial, value)

        match self._state:
            case VeluxPlugin.State.GATEWAY:
                return
            case VeluxPlugin.State.SENSOR:
                if dial != 0: 
                    return
                value = sorted((-1, value, 1))[1]
                self._sensor_counter += value
                self._sensor_counter = self._wrap(self._sensor_counter, len(self._accessories_by_type(VeluxTypes.SENSOR)))
                self._select_sensor()
            case VeluxPlugin.State.ZONES:
                if dial != 0: 
                    return
                value = sorted((-1, value, 1))[1]
                self._zone_counter += value
                self._zone_counter = self._wrap(self._zone_counter, len(self._zones))
                self._select_zone()
            case VeluxPlugin.State.ZONE_ACCESSORY_SELECT:
                if dial != 0: 
                    return
                value = sorted((-1, value, 1))[1]
                self._za_counter += value
                zone : VeluxZone = self._zones[self._zone_counter]
                self._za_counter = self._wrap(self._za_counter, len(zone.accessories))
                self._select_zone_accessory()
            case VeluxPlugin.State.ZONE_ACCESSORY_SHOW:
                match dial:
                    case 0:
                        self._state = VeluxPlugin.State.ZONE_ACCESSORY_SELECT
                    case 1:
                        z : VeluxZone = self._zones[self._zone_counter]
                        a : IAccessory = z.accessories[self._za_counter]
                        c : ICharacteristic = a.get_writeable_characteristic()
                        if (c):
                            value = (c.get_target_value() + value)
                            c.set_target_value(value)
                            self._update_screen()
                    case _:
                        pass
            case VeluxPlugin.State.SHUTTERS:
                match dial:
                    case 0:
                        value = sorted((-1, value, 1))[1]
                        self._shutter_counter += value
                        self._shutter_counter = self._wrap(self._shutter_counter, len(self._accessories_by_type(VeluxTypes.EXTERNAL_COVER)))
                        self._select_shutter()
                    case _:
                        pass
            case VeluxPlugin.State.SHUTTER_ACCESSORIES:
                match dial:
                    case 0:
                        self._state = VeluxPlugin.State.SHUTTERS
                        self._select_shutter()
                    case 1:
                        a : IAccessory = self._accessories_by_type(VeluxTypes.EXTERNAL_COVER)[self._shutter_counter]
                        c : ICharacteristic = a.get_writeable_characteristic()
                        if c is not None:
                            value = (c.get_target_value() + value)
                            c.set_target_value(value)
                            self._show_shutter()
                    case _:
                        pass
            case VeluxPlugin.State.WINDOWS:
                match dial:
                    case 0:
                        value = sorted((-1, value, 1))[1]
                        self._window_counter += value
                        self._window_counter = self._wrap(self._window_counter, len(self._accessories_by_type(VeluxTypes.VELUX_WINDOW)))
                        self._select_window()
                    case _:
                        pass
            case VeluxPlugin.State.WINDOW_ACCESSORIES:
                match dial:
                    case 0:
                        self._state = VeluxPlugin.State.WINDOWS
                        self._select_window()
                    case 1:
                        a : IAccessory = self._accessories_by_type(VeluxTypes.VELUX_WINDOW)[self._window_counter]
                        c : ICharacteristic = a.get_writeable_characteristic()
                        if c is not None:
                            value = (c.get_target_value() + value)
                            c.set_target_value(value)
                            self._show_window()
                    case _:
                        pass
            case _:
                print(self._state)
                pass

    def on_dial_pushed(self, deck, dial, state):
        super().on_dial_pushed(deck, dial,state)

        if not state: 
            return

        match self._state:
            case VeluxPlugin.State.GATEWAY:
                pass
            case VeluxPlugin.State.SENSOR:
                if dial != 0: 
                    return
                self._state = VeluxPlugin.State.SENSOR_DETAILS
                self._update_screen()
            case VeluxPlugin.State.SENSOR_DETAILS:
                if dial != 0: 
                    return
                self._state = VeluxPlugin.State.SENSOR
                self._update_screen()
            case VeluxPlugin.State.ZONES:
                if dial != 0: 
                    return
                self._state = VeluxPlugin.State.ZONE_ACCESSORY_SELECT
                self._za_counter = 0
                self._update_screen()
            case VeluxPlugin.State.ZONE_ACCESSORY_SELECT:
                if dial != 0: 
                    return
                self._state = VeluxPlugin.State.ZONE_ACCESSORY_SHOW
                self._update_screen()
            case VeluxPlugin.State.ZONE_ACCESSORY_SHOW:
                match dial:
                    case 1:
                        z : VeluxZone = self._zones[self._zone_counter]
                        a : IAccessory = z.accessories[self._za_counter]
                        success = a.update()
                        if success:
                            self._poll_environment()
                            msg = f"Updating : {a.name}"
                            self._notify(msg, True, 5)
                    case 2:
                        z : VeluxZone = self._zones[self._zone_counter]
                        a : IAccessory = z.accessories[self._za_counter]
                        success, msg = a.toggle()
                        if success:
                            self._poll_environment()
                            self._notify(msg, True, 5)
                    case _:
                        pass
            case VeluxPlugin.State.SHUTTERS:
                match dial:
                    case 0:
                        self._state = VeluxPlugin.State.SHUTTER_ACCESSORIES
                        self._update_screen()
                    case 1:
                        a : IAccessory = self._accessories_by_type(VeluxTypes.EXTERNAL_COVER)[self._shutter_counter]
                        success, msg = a.toggle()
                        if success:
                            self._poll_environment()
                            self._notify(msg, True, 5)
                    case 2:
                        a_l : list[IAccessory] = self._accessories_by_type(VeluxTypes.EXTERNAL_COVER)
                        msg : str = f"Toggling {a_l} shutters"
                        success_all : bool = True
                        for a in a_l:
                            success, msg = a.toggle()
                            if not success:
                                success_all = False
                                self._notify(msg, True, 5)
                                self._log.error(msg)
                                break
                        if success_all:
                            self._poll_environment()
                            self._notify(msg, True, 5)
                    case _:
                        pass
            case VeluxPlugin.State.SHUTTER_ACCESSORIES:
                match dial:
                    case 1:
                        a : IAccessory = self._accessories_by_type(VeluxTypes.EXTERNAL_COVER)[self._shutter_counter]
                        success : bool = a.update()
                        if success:
                            self._poll_environment()
                            msg = f"Updating : {a.name}"
                            self._notify(msg, True, 5)
                    case 2:
                        a : IAccessory = self._accessories_by_type(VeluxTypes.EXTERNAL_COVER)[self._shutter_counter]
                        success, msg = a.toggle()
                        if success:
                            self._poll_environment()
                            self._notify(msg, True, 5)
                    case _:
                        pass
            case VeluxPlugin.State.WINDOWS:
                match dial:
                    case 0:
                        self._state = VeluxPlugin.State.WINDOW_ACCESSORIES
                        self._show_window()
                        self._update_screen()
                    case 1:
                        window : IAccessory = self._accessories_by_type(VeluxTypes.VELUX_WINDOW)[self._window_counter]
                        success, msg = window.toggle()
                        if success:
                            self._poll_environment()
                            self._notify(msg, True, 5)
                    case 2:
                        a_l : list[IAccessory] = self._accessories_by_type(VeluxTypes.VELUX_WINDOW)
                        msg : str = f"Toggling {len(a_l)} windows"
                        success_all : bool = True
                        for a in a_l:
                            success, msg = a.toggle()
                            if not success:
                                self._notify(msg, True, 5)
                                self._log.error(msg)
                                success_all = False
                                break
                        if success_all:
                            self._poll_environment()
                            self._notify(msg, True, 5)
                    case _:
                        pass
            case VeluxPlugin.State.WINDOW_ACCESSORIES:
                match dial:
                    case 1:
                        a : IAccessory = self._accessories_by_type(VeluxTypes.VELUX_WINDOW)[self._window_counter]
                        success = a.update()
                        if success:
                            self._poll_environment()
                            msg = f"Updating : {a.name}"
                            self._notify(msg, True, 5)
                    case 2:
                        a : IAccessory = self._accessories_by_type(VeluxTypes.VELUX_WINDOW)[self._shutter_counter]
                        success, msg = a.toggle()
                        if success:
                            self._poll_environment()
                            self._notify(msg, True, 5)
                    case _:
                        pass
            case _:
                print(self._state)
                pass

    def on_button_press(self, deck, key, key_state):
        super().on_button_press(deck, key, key_state)
        if not key_state: 
            return

        match key:
            case VeluxPlugin.Buttons.GATEWAY.value:
                if self._state == VeluxPlugin.State.GATEWAY:
                    self._state = VeluxPlugin.State.NONE
                else:
                    self._state = VeluxPlugin.State.GATEWAY
                pass
            case VeluxPlugin.Buttons.SENSOR.value:
                if self._state == VeluxPlugin.State.SENSOR:
                    self._state = VeluxPlugin.State.NONE
                else:
                    self._state = VeluxPlugin.State.SENSOR
                    self._sensor_counter = 0
                pass
            case VeluxPlugin.Buttons.ZONES.value:
                if self._state == VeluxPlugin.State.ZONES:
                    self._state = VeluxPlugin.State.NONE
                elif self._state == VeluxPlugin.State.ZONE_ACCESSORY_SHOW:
                    self._state = VeluxPlugin.State.ZONE_ACCESSORY_SELECT
                elif self._state == VeluxPlugin.State.ZONE_ACCESSORY_SELECT:
                    self._state = VeluxPlugin.State.ZONES
                else:
                    self._state = VeluxPlugin.State.ZONES
                    self._zone_counter = 0
                    self._za_counter = 0
            case VeluxPlugin.Buttons.SHUTTERS.value:
                if self._state == VeluxPlugin.State.SHUTTERS:
                    self._state = VeluxPlugin.State.NONE
                else:
                    self._state = VeluxPlugin.State.SHUTTERS
                    self._shutter_counter = 0
            case VeluxPlugin.Buttons.WINDOWS.value:
                if self._state == VeluxPlugin.State.WINDOWS:
                    self._state = VeluxPlugin.State.NONE
                else:
                    self._state = VeluxPlugin.State.WINDOWS
                    self._window_counter = 0
            case _:
                pass
        self._update_screen()

    @property
    def accessories(self) -> list[:IAccessory]:
        return self._accessories

    def _initialize(self):
        self._state = VeluxPlugin.State.NONE
        self._sensor_counter = 0
        self._zone_counter = 0
        self._za_counter = 0
        self._shutter_counter = 0
        self._window_counter = 0

    def _accessories_by_type(self, type : VeluxTypes) -> list[:IAccessory]:
        return [a for a in self._accessories if a.type == type]

    def _notify(self, message : str, reset_after : bool = False, wait : float = 2.0):
        self._render(message)
        if reset_after:
            timer = threading.Timer(wait, self._update_screen)
            timer.start()

    def _update_buttons(self):
        # layout the images
        self._app.set_button_image(VeluxPlugin.Buttons.GATEWAY.value, self._images[VeluxPlugin.Images.GATEWAY.value])
        self._app.set_button_image(VeluxPlugin.Buttons.SENSOR.value, self._images[VeluxPlugin.Images.SENSOR.value])
        self._app.set_button_image(VeluxPlugin.Buttons.ZONES.value, self._images[VeluxPlugin.Images.ZONES.value])
        self._app.set_button_image(VeluxPlugin.Buttons.SHUTTERS.value, self._images[VeluxPlugin.Images.SHUTTER.value])
        self._app.set_button_image(VeluxPlugin.Buttons.WINDOWS.value, self._images[VeluxPlugin.Images.WINDOW.value])

        for x in range(VeluxPlugin.Buttons.WINDOWS.value + 1, self._app.num_buttons):
            self._app.set_button_image(x, self._images[VeluxPlugin.Images.BLANK.value])

    def _update_screen(self):
        if len(self._accessories) == 0: 
            return
        match self._state:
            case VeluxPlugin.State.NONE:
                gateway = self._accessories_by_type(VeluxTypes.GATEWAY)[0]
                msg = f"{gateway.model} - {gateway.serial_number}"
                self._notify(msg)
            case VeluxPlugin.State.GATEWAY:
                gateway = self._accessories_by_type(VeluxTypes.GATEWAY)[0]
                self._notify(gateway.get_formatted_string())
            case VeluxPlugin.State.SENSOR:
                self._select_sensor()
            case VeluxPlugin.State.SENSOR_DETAILS:
                self._show_sensor()
            case VeluxPlugin.State.ZONES:
                self._select_zone()
            case VeluxPlugin.State.ZONE_ACCESSORY_SELECT:
                self._select_zone_accessory()
            case VeluxPlugin.State.ZONE_ACCESSORY_SHOW:
                self._show_zone_accessory()
            case VeluxPlugin.State.SHUTTERS:
                self._select_shutter()
            case VeluxPlugin.State.SHUTTER_ACCESSORIES:
                self._show_shutter()
            case VeluxPlugin.State.WINDOWS:
                self._select_window()
            case VeluxPlugin.State.WINDOW_ACCESSORIES:
                self._show_window()
            case _:
                self._notify(self._state)

    def _select_zone(self) -> None:
        zone = self._zones[self._zone_counter]
        num_z = len(self._zones)
        msg = f"{zone.name} ({self._zone_counter + 1}/{num_z})\n"
        self._notify(msg)
    
    def _select_zone_accessory(self) -> None:
        zone : VeluxZone  = self._zones[self._zone_counter]
        num_z = len(self._zones)
        accessory : IAccessory = zone.accessories[self._za_counter]
        self._notify(f"{zone.name}({self._zone_counter + 1}/{num_z})\n:- {accessory.name}")

    def _show_zone_accessory(self) -> None:
        zone : VeluxZone  = self._zones[self._zone_counter]
        accessory : IAccessory = zone.accessories[self._za_counter]
        self._notify(accessory.get_formatted_string())

    def _select_sensor(self) -> None:
        a_l : list[:IAccessory] = self._accessories_by_type(VeluxTypes.SENSOR)
        num_a : int = len(a_l)
        sensor = a_l[self._sensor_counter]
        msg = f"Sensor : ({self._sensor_counter + 1}/{num_a})\n:- {sensor.name}"
        self._notify(msg)

    def _show_sensor(self) -> None:
        sensor = self._accessories_by_type(VeluxTypes.SENSOR)[self._sensor_counter]
        msg = sensor.get_formatted_string()
        self._notify(msg)

    def _select_shutter(self):
        a_l : list[:IAccessory] = self._accessories_by_type(VeluxTypes.EXTERNAL_COVER)
        num_a : int = len(a_l)
        shutter = a_l[self._shutter_counter]
        msg = f"Shutter : ({self._shutter_counter + 1}/{num_a})\n:- {shutter.name}"
        self._notify(msg)
    
    def _show_shutter(self):
        shutter = self._accessories_by_type(VeluxTypes.EXTERNAL_COVER)[self._shutter_counter]
        msg = shutter.get_formatted_string()
        self._notify(msg)

    def _select_window(self):
        a_l : list[:IAccessory] = self._accessories_by_type(VeluxTypes.VELUX_WINDOW)
        num_a : int = len(a_l)
        window = a_l[self._window_counter]
        msg = f"Window : ({self._window_counter + 1}/{num_a})\n:- {window.name}"
        self._notify(msg)
    
    def _show_window(self):
        window = self._accessories_by_type(VeluxTypes.VELUX_WINDOW)[self._window_counter]
        msg = window.get_formatted_string()
        self._notify(msg)
