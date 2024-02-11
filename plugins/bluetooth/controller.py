
from .shared import BluetoothError, BluetoothCtlInterface

import json
import logging
import os

class BluetoothController(BluetoothCtlInterface):

    DEFAULT_TIMEOUT : int = 10

    def __init__(self, mac_address : str = None) -> None:
        super().__init__()
        self._mac_address : str = mac_address
        self._name : str = mac_address
        self._powered : bool = False
        self._discoverable : bool = False
        self._pairable : bool = False
        self._info : list[str] = None
        self._log : logging.Logger = logging.getLogger(__name__)
        self._log.setLevel(os.environ.get("LOGLEVEL", "INFO"))

    @property
    def mac_address(self) -> str:
        return self._mac_address

    @property
    def name(self) -> str:
        return self._name

    @property
    def powered(self) -> bool:
        return self._powered

    @property
    def discoverable(self) -> bool:
        return self._discoverable

    @property
    def pairable(self) -> bool:
        return self._pairable

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, BluetoothController):
            return self.mac_address == other.mac_address
        return NotImplemented

    def __str__(self) -> str:
        return json.dumps(self.toJSON())

    def toJSON(self) -> dict:
        return {
            "name" : self.name,
            "mac_address" : self.mac_address,
            "powered": self._powered, 
            "discoverable": self._discoverable,
            "pairable": self._pairable
        }

    def refresh(self) -> bool:
        try:

            if self._mac_address is None:
                self._log.error("Failed to find default controller")
                return False

            controller_info : list[str] = self._run_command(f"show {self._mac_address}")
            self._info = []
            for line in controller_info:
                line = line.strip()
                if line.startswith("Controller"):
                    # we already know the mac address by here
                    pass
                elif line.startswith("Name"):
                    self._name = " ".join(line.split(":")[1:]).strip()
                elif line.startswith("Powered"):
                    self._powered = line.split(":")[1].strip().lower() == "yes"
                elif line.startswith("Discoverable"):
                    self._discoverable = line.split(":")[1].strip().lower() == "yes"
                elif line.startswith("Pairable"):
                    self._pairable = line.split(":")[1].strip().lower() == "yes"
                else:
                    self._info.append(line)

            return True
        except Exception as ex:
            self._log.error(ex)
            return False

    def power_on(self) -> bool:
        try:
            if self.powered:
                return True
            result : list[str] = self._run_command("power on")
            self.refresh()
            self._log.debug(result)
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False
    
    def power_off(self) -> bool:
        try:
            if not self.powered:
                return True
            result : list[str] = self._run_command("power off")
            self.refresh()
            self._log.debug(result)
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False

    def make_discoverable(self, timeout = DEFAULT_TIMEOUT) -> bool:
        try:
            result : list[str] = self._run_command("discoverable on", timeout)
            self._log.debug(result)
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False

