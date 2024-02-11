from .shared import BluetoothError, BluetoothCtlInterface

import json
import logging
import os

class BluetoothDevice(BluetoothCtlInterface):

    def __init__(self, mac_address : str = None) -> None:
        super().__init__()
        # default the name to mac address, in case it is None when we parse for it]
        self._name : str = mac_address
        self._mac_address : str = mac_address
        self._connected : bool = False
        self._paired : bool = False
        self._trusted : bool = False
        self._info : list[str] = None
        self._pairing : bool = False
        self._log : logging.Logger = logging.getLogger(__name__)
        self._log.setLevel(os.environ.get("LOGLEVEL", "INFO"))

    @property
    def name(self) -> str:
        return self._name

    @property
    def mac_address(self) -> str:
        return self._mac_address

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def paired(self) -> bool:
        return self._paired
    
    @property
    def trusted(self) -> bool:
        return self._trusted

    @property
    def info(self) -> list[str]:
        return self._info

    @property
    def pairing(self) -> bool:
        return self._pairing

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, BluetoothDevice):
            return self.mac_address == other.mac_address
        return NotImplemented

    def __str__(self) -> str:
        return json.dumps(self.toJSON())

    def toJSON(self) -> dict:
        return {
            "name" : self.name,
            "mac_address" : self.mac_address,
            "connected" : self.connected
        }

    def refresh(self) -> bool:
        try:
            if self._mac_address is None:
                raise BluetoothError("No mac address specified")
            results : list[str] = self._run_command(f"info {self.mac_address}")
            self._info = []
            for line in results:
                line = line.strip()
                if line.startswith("Device"):
                    # we already know the mac address by here
                    continue
                elif line.startswith("Name:"):
                    self._name = line.split(":")[1].strip()
                elif line.startswith("Paired:"):
                    self._paired = line.split(":")[1].strip().lower() == "yes"
                elif line.startswith("Trusted:"):
                    self._trusted = line.split(":")[1].strip().lower() == "yes"
                elif line.startswith("Connected:"):
                    self._connected = line.split(":")[1].strip().lower() == "yes"
                else:
                    # only add key value stuff to info, or we pick up loads of junk
                    pos : int = line.find(":")
                    if pos > 0 and pos < len(line):
                        line = line[pos + 1:].strip()
                        self._info.append(line)

            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False

    def disconnect(self) -> bool:
        try:
            if not self._connected:
                return True
            self._log.debug(f"Disconnecting {self.name} : {self.mac_address}")
            results : list[str] = self._run_command(f"disconnect {self.mac_address}")
            self._connected = not self._parse_results(["successful", "disconnected"], results)
            self._log.debug(f"Device {self.name} connected : {self.connected}")
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False

    def connect(self,) -> bool:
        try:
            if self._connected:
                self.log.debug("Already connected, returning")
                return True

            if not self.paired:
                self.pair()
            if not self.trusted:
                self.trust()

            self._log.debug(f"Connecting to {self.name}")
            results : list[str] = self._run_command(f"connect {self.mac_address}")
            self._connected = self._parse_results(["connection", "successful"], results)
            if not self.connected:
                self._log.error(results)
                return False
            self._log.debug(f"Bluetooth connected to : {self.name}")
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            self._connected_device = None
            return False

    def trust(self) -> bool:
        try:
            result : list[str] = self._run_command(f"trust {self.mac_address}")
            self._log.debug(result)
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False

    def pair(self) -> bool:
        try:
            self._pairing = True
            result : list[str] = self._run_command(f"pair {self.mac_address}")
            self._log.debug(result)
            self._pairing = False
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            self._pairing = False
            return False

    def cancel_pairing(self) -> bool:
        try:
            if not self._pairing: 
                return True
            result : list[str] = self._run_command(f"cancel-pairing {self._mac_address}")
            self._log.debug(result)
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False
