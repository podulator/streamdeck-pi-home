from ..IPlugin import IPlugin
from enum import IntEnum
from .helper import BluetoothManager, BluetoothController, BluetoothDevice
import threading

class BluetoothPlugin(IPlugin):

    class State(IntEnum):
        NONE = 0
        CONNECTED = 1
        SCANNING = 2
        DELETING = 3

    class Buttons(IntEnum):
        BACK = 0
        CONNECT = 1
        SCAN = 2
        ON = 3
        DELETE = 4
        INFO = 5
        AUTO = 6
        BLANK_1 = 7

    image_keys : list [str]= [ "connected.png", "scanning.png", "on.png", "delete.png", "info.png", "auto.png", "blank.png" ]
    image_state_keys : list[str] = [ "disconnected.png", "scanned.png" , "off.png", "manual.png" ]

    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)
        self._state = BluetoothPlugin.State.NONE
        self._images : list[bytes] = None
        self._state_images : list[bytes] = None
        self._device_index : int = 0
        self._running_as_daemon : bool = False
        self._bt : BluetoothManager = BluetoothManager(app, self._callback)
        self._notify_timer : threading.Timer = None
        self._connect_thread : threading.Thread = None
        self._help_message = "Bluetooth plugin\nBack | Status | Scan | Power\nForget | Info | Toggle Auto | N/A"

    def run_as_daemon(self) -> None:
        super().run_as_daemon()

        try:
            self._running_as_daemon = True
            auto_connect : bool = self._config.get("auto-connect", False)
            preferred_device : str = self._config.get("preferred-device", None)
            # copy, so the preferred device is not written back into the saved config
            allowed_devices : list[str] = list(self._config.get("allowed-devices", None) or [])

            if auto_connect and allowed_devices:
                if preferred_device:
                    allowed_devices = [preferred_device] + [d for d in allowed_devices if d != preferred_device]
                # we might have enough info to auto start
                self._bt.initialize()
                if self._bt.controller is not None and self._bt.controller.powered:
                    self._log.debug("We have a powered controller, good to go")
                    threading.Thread(target = self._bt.daemon_connect, args=(allowed_devices,), daemon = True).start()
                else:
                    self._log.debug("We don't have a valid controller")
        except Exception as ex:
            self._log.error(f"Failed to start up as a daemon :: {ex}")
            self._running_as_daemon = False

    def activate(self) -> bool:
        if not super().activate():
            return False
        try:
            self._state = BluetoothPlugin.State.NONE
            self._device_index = 0
            self._bt.initialize()
            self._bt.threaded_scan()
            self._show_default()
        except Exception as ex:
            self._log.error(f"Failed to activate :: {ex}")
            self._activated = False
        return self._activated

    def deactivate(self):
        super().deactivate()

    def destroy(self):
        super().destroy()
        self._bt.destroy()

    def on_button_press(self, deck, key, key_state):
        super().on_button_press(deck, key, key_state)

        # only press down matters
        if not key_state:
            return

        match key:
            case BluetoothPlugin.Buttons.BACK:
                pass
            case BluetoothPlugin.Buttons.CONNECT:
                if self._bt.connected:
                    self._render("Bluetooth\nDisconnecting...")
                    self._bt.disconnect_all()
                    self._state = BluetoothPlugin.State.NONE
                else:
                    self._state = BluetoothPlugin.State.CONNECTED
                    self._show_devices()
                self._update_buttons()
            case BluetoothPlugin.Buttons.SCAN:
                if not self._bt.scanning:
                    self._render("Bluetooth\nScanning...")
                    self._bt.threaded_scan()
                self._update_buttons()
            case BluetoothPlugin.Buttons.ON:
                if self._bt.controller is None:
                    self._render("Bluetooth\nNo controller found")
                elif self._bt.controller.powered:
                    self._bt.controller.power_off()
                else:
                    self._bt.controller.power_on()
                self._update_buttons()
            case BluetoothPlugin.Buttons.DELETE:
                if self._state == BluetoothPlugin.State.DELETING:
                    self._state = BluetoothPlugin.State.NONE
                    self._show_default()
                else:
                    self._state = BluetoothPlugin.State.DELETING
                    self._show_devices()
                pass
            case BluetoothPlugin.Buttons.INFO:
                c : BluetoothController = self._bt.controller
                if c is not None:
                    msg = f"Name : {c.name}\nMAC address : {c.mac_address}\nPowered : {c.powered}"
                    self._render(msg)
                pass
            case BluetoothPlugin.Buttons.AUTO:
                self._config["auto-connect"] = not self._config.get("auto-connect", False)
                self._update_buttons()
                pass
            case _:
                pass

    def on_dial_turned(self, deck, dial, value):
        super().on_dial_turned(deck, dial, value)

        match self._state:
            case BluetoothPlugin.State.NONE:
                pass
            case BluetoothPlugin.State.CONNECTED:
                if dial != 0:
                    return
                self._device_index += sorted((-1, value, 1))[1]
                self._device_index = self._wrap(self._device_index, len(self._bt.devices))
                self._show_devices()
            case BluetoothPlugin.State.DELETING:
                if dial != 0:
                    return
                self._device_index += sorted((-1, value, 1))[1]
                self._device_index = self._wrap(self._device_index, len(self._bt.devices))
                self._show_devices()
            case _:
                pass

    def on_dial_pushed(self, deck, dial, state):
        super().on_dial_pushed(deck, dial, state)

        if not state:
            return
        
        try:
            match self._state:
                case BluetoothPlugin.State.NONE:
                    pass
                case BluetoothPlugin.State.CONNECTED:
                    if dial != 0: 
                        return
                    device : BluetoothDevice = self._selected_device()
                    if device is None:
                        return
                    if self._connect_thread is not None and self._connect_thread.is_alive():
                        self._render("Bluetooth\nStill connecting...")
                        return
                    # pairing a new device can take ~40s, so keep the deck responsive; the manager notifies the result
                    self._render(f"Bluetooth\nConnecting to\n{device.name}")
                    self._connect_thread = threading.Thread(target = self._bt.connect, args = (device,), daemon = True)
                    self._connect_thread.start()
                    self._update_buttons()
                case BluetoothPlugin.State.DELETING:
                    if dial != 0:
                        return
                    device = self._selected_device()
                    if device is not None:
                        self._render(f"Bluetooth\nForgetting\n{device.name}")
                        self._bt.remove(device)
                    self._update_buttons()
                case _:
                    pass
        except Exception as ex:
            self._log.error(ex)

    def _selected_device(self) -> BluetoothDevice:
        devices : list[BluetoothDevice] = self._bt.devices
        if not devices:
            return None
        if self._device_index >= len(devices):
            self._device_index = 0
        return devices[self._device_index]

    def _show_devices(self):
        if not self._activated: 
            return

        try:
            device : BluetoothDevice = self._selected_device()
            if device is None:
                self._render("Bluetooth\nNo devices found\nPress Scan")
                return
            match self._state:
                case BluetoothPlugin.State.CONNECTED:
                    msg = f"Connect to device\n{device.name}"
                    self._render(msg)
                case BluetoothPlugin.State.DELETING:
                    msg = f"Forget device\n{device.name}"
                    self._render(msg)
                case _:
                    pass
        except Exception as ex:
            self._log.error(ex)

    def _callback(self, data : str):
        if not self._activated:
            return
        self._render(data)
        self._update_buttons()
        if self._notify_timer is not None:
            self._notify_timer.cancel()
        self._notify_timer = threading.Timer(2, self._show_default)
        self._notify_timer.start()

    def _show_default(self):
        if not self._activated: 
            return
        if self._images is None:
            self._images = []
            self._state_images = []
            self._load_images(self._images, BluetoothPlugin.image_keys)
            self._load_images(self._state_images, BluetoothPlugin.image_state_keys)

        try:
            for n in range (0, len(BluetoothPlugin.Buttons) - 1):
                self._app.set_button_image(n + 1, self._images[n])

            self._update_buttons()
            if self._bt.controller is None:
                self._render("Bluetooth\nNo controller found")
                return
            status : str = "On" if self._bt.controller.powered else "Off"
            if self._bt.connected:
                self._render(
                    f"Bluetooth - Powered {status}\nConnected\n{self._bt.controller.name} <-> {self._bt.connected_device.name}"
                )
            else:
                self._render(
                    f"Bluetooth - Powered {status}\nDisconnected\n"
                )
        except Exception as ex:
            self._log.error(f"Failed to show default screen :: {ex}")

    def _update_buttons(self):
        if not self._activated: 
            return
        try:
            if self._state_images is None or self._images is None: 
                return

            # handle toggle buttons
            if self._bt.connected:
                self._app.set_button_image(BluetoothPlugin.Buttons.CONNECT.value, self._images[BluetoothPlugin.Buttons.CONNECT.value - 1])
            else:
                self._app.set_button_image(BluetoothPlugin.Buttons.CONNECT.value, self._state_images[0])

            if self._bt.scanning:
                self._app.set_button_image(BluetoothPlugin.Buttons.SCAN.value, self._images[BluetoothPlugin.Buttons.SCAN.value - 1])
            else:
                self._app.set_button_image(BluetoothPlugin.Buttons.SCAN.value, self._state_images[1])

            if self._bt.controller is not None and self._bt.controller.powered:
                self._app.set_button_image(BluetoothPlugin.Buttons.ON.value, self._images[BluetoothPlugin.Buttons.ON.value - 1])
            else:
                self._app.set_button_image(BluetoothPlugin.Buttons.ON.value, self._state_images[2])

            if self._config.get("auto-connect", False):
                self._app.set_button_image(BluetoothPlugin.Buttons.AUTO.value, self._images[BluetoothPlugin.Buttons.AUTO.value - 1])
            else:
                self._app.set_button_image(BluetoothPlugin.Buttons.AUTO.value, self._state_images[3])

            self._app.set_button_image(BluetoothPlugin.Buttons.BLANK_1.value, self._images[BluetoothPlugin.Buttons.BLANK_1.value - 1])
        except Exception as ex:
            self._log.error(f"Failed to update buttons :: {ex}")