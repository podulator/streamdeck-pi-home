from __future__ import annotations
from .shared import BluetoothError, BluetoothCtlInterface
from .controller import BluetoothController
from .device import BluetoothDevice
from threading import Thread
from typing import Callable

import logging
import os
import time

class BluetoothManager(BluetoothCtlInterface):
    DEFAULT_TIMEOUT : int = 10
    BACKOFF_MAX: int = 120

    def __init__(self, app, callback : Callable):
        super().__init__()
        self._callback : Callable = callback
        self._app = app
        self._log : logging.Logger = logging.getLogger(__name__)
        self._log.setLevel(os.environ.get("LOGLEVEL", "INFO"))
        self._available_devices : list[BluetoothDevice] = []
        self._controller : BluetoothController = None
        self._connected_device : BluetoothDevice = None
        self._scanning : bool = False
        self._is_daemon : bool = False
        self._backoff: int = 0
        self._debug : bool = False

    @property
    def connected(self) -> bool:
        return False if self._connected_device is None else True

    @property
    def connected_device(self) -> BluetoothDevice:
        return self._connected_device

    @property
    def devices(self) -> list[BluetoothDevice]:
        if self._available_devices is None:
            return []
        return self._available_devices

    @property
    def scanning(self) -> bool:
        return self._scanning

    @property
    def controller(self) -> BluetoothController:
        return self._controller

    def refresh(self) -> bool:
        return True

    def _notify(self, message):
        if self._callback is not None:
            self._callback(message)

    def _scan(self, timeout = DEFAULT_TIMEOUT) -> None:
        try:
            self._scanning = True
            self._log.info(f"Bluetooth - Starting scanning for {timeout} seconds")
            self._controller.power_on()
            self._run_command("scan on", timeout)
            self._resolve_devices()
            self._log.info(f"Bluetooth - Scan completed : Found {len(self._available_devices)} devices")
            for device in self._available_devices:
                self._log.debug(str(device))
            self._notify(f"Bluetooth\nScan completed\nFound {len(self._available_devices)} devices")
        except (BluetoothError, Exception) as e:
            self._log.error(e)
        finally:
            self._scanning = False

    def _disconnect(self, device : BluetoothDevice) -> bool:
        try:
            device.disconnect()
            if device == self._connected_device and device.connected == False:
                self._connected_device = None
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False

    def destroy(self) -> None:
        try:
            self._is_daemon = False
            self.disconnect_all()
            self._available_devices = None
            self._connected_device = None
        except (BluetoothError, Exception) as e:
            self._log.error(e)

    def threaded_scan(self, timeout = DEFAULT_TIMEOUT) -> bool:
        try:
            if self._scanning: 
                self._log.debug("Scan requested while already scanning")
                return False
            thread : Thread = Thread(target = self._scan, args = ((timeout,)))
            thread.start()
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False

    def _resolve_devices(self) -> bool:

        try:

            self._log.debug("Building device ground truth")
            available_devices : list[BluetoothDevice] = []
            results : list[str] = self._run_command("devices")
            for line in results:
                line = line.strip()
                if not line.startswith("Device"): 
                    continue
                line = line[len("Device"):].strip()
                parts : list[str] = line.split(" ")
                if len(parts) < 2: 
                    continue

                mac_address : str = parts.pop(0)
                device = BluetoothDevice(mac_address)
                if device.refresh():
                    available_devices.append(device)

            self._log.debug(f"Found {len(available_devices)} devices")

            for device in available_devices:
                if device.connected and self._connected_device is None:
                    self._log.info(f"We are connected to {device.name}")
                    self._connected_device = device

            self._available_devices = available_devices
            return True

        except Exception as ex:
            self._log.error(ex)
            return False

    def initialize(self) -> None:
        try:
            if self._controller is None:
                results : list[str] = self._run_command("list")
                for line in results:
                    if line.endswith("[default]"):
                        mac_address : str = line.split(" ")[1]
                        controller : BluetoothController = BluetoothController(mac_address)
                        if controller.refresh():
                            self._controller = controller
                            self._log.info(f"Found bluetooth controller :: {self._controller.name} - ({self._controller.mac_address})")
                        break
            else:
                self._controller.refresh()
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            self._controller = None

    # basic toggle command section

    def remove(self, device) -> bool:
        try:
            result : list[str] = self._run_command(f"remove {device.mac_address}")
            self._log.debug(result)
            for d in self._available_devices:
                if d == device:
                    self._available_devices.remove(d)
            self._notify(f"Bluetooth\nDevice removed\n{device.name}")
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False

    def daemon_connect(self, allowed_devices : list[str]) -> bool:
        try:
            counter : int = 0
            threshold : int = 10
            self._is_daemon = True

            device_list : str = "', '".join(allowed_devices)
            self._log.info(f"Bluetooth allowed devices : '{device_list}'")

            while self._is_daemon:
                counter += 1
                if counter > threshold:
                    counter = 0
                    if self._connected_device is None:
                        self._scan(threshold - 2)
                        if self._connected_device is None:
                            self._log.debug(f"Bluetooth available devices : {', '.join([d.name for d in self._available_devices])}")
                            for a in allowed_devices:
                                for d in self._available_devices:
                                    if d.name == a:
                                        if self.connect(d):
                                            self._backoff = 30
                                            break
                                        self._log.info(f"Connection to device {d.name} failed")
                                        time.sleep(self._backoff)

                                if self._connected_device is not None:
                                    # successful connection
                                    break
                    else:
                        # check if we're still really connected
                        self._log.debug(f"Refreshing device status :: {self._connected_device.mac_address}")
                        self._connected_device.refresh()
                        if not self._connected_device.connected:
                            self._log.debug("Device disconnected, forcing a reset")
                            self._disconnect(self._connected_device)
                        else:
                            self._backoff = 30

                if not self.connected_device.connected:
                    self._backoff = min(self._backoff + 1, BluetoothManager.BACKOFF_MAX)
                self._log.debug(f"Bluetooth daemon loop backoff sleep time is {self._backoff} seconds")
                time.sleep(self._backoff)

            self._log.debug("Daemon connection stopped")

        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False

    def connect(self, device : BluetoothDevice) -> bool:
        try:
            self._log.debug(f"Bluetooth connecting to {device.name} :: {device.mac_address}")
            if device.connect():
                self._connected_device = device
                self._notify(f"Bluetooth\nConnected to\n{device.name}")
                return True
            return False
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            self._connected_device = None
            return False

    def disconnect_all(self) -> bool:
        try:
            for d in self._available_devices:
                if d.pairing:
                    d.cancel_pairing()
                d.disconnect()
            self._connected_device = None
            self._notify("Bluetooth\nDisconnected")
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False
