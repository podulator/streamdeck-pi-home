from .shared import BluetoothError, BluetoothCtlInterface

import json
import logging
import os
import time

class BluetoothDevice(BluetoothCtlInterface):

    # speakers etc. have no input, so let BlueZ do "Just Works" pairing without prompting
    AGENT : str = "NoInputNoOutput"
    # BlueZ drops unpaired devices from its cache ~30s after discovery stops, so rescan right before pairing
    PRE_PAIR_SCAN : int = 5
    PAIR_TIMEOUT : int = 30
    CONNECT_TIMEOUT : int = 20
    CONNECT_ATTEMPTS : int = 2
    # re-pair a paired device that refuses to connect, at most once per cooldown so we can't loop forgetting it
    STALE_PAIRING_HINTS : tuple[str, ...] = ("br-connection-unknown", "key-missing", "authenticationfailed", "authentication failed", "permission denied")
    REPAIR_COOLDOWN : int = 600
    # keyed by MAC, as the manager builds fresh device objects on every scan
    _last_repairs : dict[str, float] = {}

    def __init__(self, mac_address : str = None, name : str = "") -> None:
        super().__init__()
        # default the name to empty, and use the public getter to return the mac address if it is empty
        self._name : str = ""
        # name from the "devices" listing, used until "info" reports a real Name
        self._fallback_name : str = name or ""
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
        return self._name or self._fallback_name or self._mac_address

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

    @staticmethod
    def normalise_mac(value : str) -> str:
        return (value or "").strip().upper().replace("-", ":")

    def matches(self, entry : str) -> bool:
        """True if a config entry names this device, by MAC address (aa:bb.., AA-BB..) or by name / alias.
        A MAC entry keeps matching while BlueZ briefly has no name for the device, e.g. just after pairing."""
        if not entry:
            return False
        if BluetoothDevice.normalise_mac(entry) == BluetoothDevice.normalise_mac(self._mac_address):
            return True
        entry = entry.strip()
        return entry in (self._name, self._fallback_name)

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

            paired: bool = False
            trusted: bool = False
            connected: bool = False

            for line in results:
                line = line.strip()
                if line.startswith("Device"):
                    # we already know the mac address by here
                    continue
                elif line.startswith("Name:"):
                    if not self._name:
                        self._name = line.split(":", 1)[1].strip()
                elif line.startswith("Alias:"):
                    if not self._fallback_name:
                        self._fallback_name = line.split(":", 1)[1].strip()
                elif line.startswith("Paired:"):
                    paired = line.split(":")[1].strip().lower() == "yes"
                elif line.startswith("Trusted:"):
                    trusted = line.split(":")[1].strip().lower() == "yes"
                elif line.startswith("Connected:"):
                    connected = line.split(":")[1].strip().lower() == "yes"
                else:
                    # only add key value stuff to info, or we pick up loads of junk
                    pos : int = line.find(":")
                    if pos > 0 and pos < len(line):
                        line = line[pos + 1:].strip()
                        self._info.append(line)

            self._paired = paired
            self._trusted = trusted
            self._connected = connected
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

    def _connect_attempts(self) -> tuple[bool, list[str]]:
        errors : list[str] = []
        for attempt in range(1, BluetoothDevice.CONNECT_ATTEMPTS + 1):
            try:
                self._log.debug(f"Connecting to {self.name} (attempt {attempt})")
                results : list[str] = self._run_command(f"connect {self.mac_address}", run_timeout = BluetoothDevice.CONNECT_TIMEOUT)
                self._connected = self._parse_results(["connection", "successful"], results)
                if self._connected:
                    return True, errors
                self._log.error(results)
                errors.append("\n".join(results))
            except BluetoothError as e:
                self._log.error(e)
                errors.append(str(e))
            # freshly paired devices often refuse the first connect while the profiles settle
            if attempt < BluetoothDevice.CONNECT_ATTEMPTS:
                time.sleep(2)
        return False, errors

    def _looks_like_stale_pairing(self, errors : list[str]) -> bool:
        # the remote dropped our stored link key (reset, or paired to something else since): the ACL link comes
        # up, then encryption is refused. bluetoothctl only shows br-connection-unknown; bluetoothd logs EACCES.
        # page-timeout means the device simply didn't answer (off / out of range), which re-pairing can't fix.
        if not errors:
            return False
        text : str = " ".join(errors).lower()
        if "page-timeout" in text:
            return False
        return any(hint in text for hint in BluetoothDevice.STALE_PAIRING_HINTS)

    def _repair(self) -> bool:
        BluetoothDevice._last_repairs[self._mac_address] = time.monotonic()
        self._log.warning(f"{self.name} refused a paired connection, its pairing looks stale : forgetting and re-pairing")
        try:
            self._run_command(f"remove {self.mac_address}")
        except BluetoothError as e:
            self._log.error(e)
        self._paired = False
        self._trusted = False
        if not self.pair():
            self._log.error(f"Re-pairing with {self.name} failed; it needs to be discoverable (not connected to another source)")
            return False
        self.trust()
        return True

    def connect(self) -> bool:
        try:
            if self._connected:
                self._log.debug("Already connected, returning")
                return True

            was_paired : bool = self.paired
            if not self.paired:
                if not self.pair():
                    self._log.error(f"Pairing with {self.name} failed, not connecting")
                    return False
            if not self.trusted:
                self.trust()

            connected, errors = self._connect_attempts()

            if not connected and was_paired and self._looks_like_stale_pairing(errors):
                last : float = BluetoothDevice._last_repairs.get(self._mac_address)
                since : float = None if last is None else time.monotonic() - last
                if since is not None and since < BluetoothDevice.REPAIR_COOLDOWN:
                    self._log.info(f"Not re-pairing {self.name} again yet ({int(since)}s since the last try)")
                elif self._repair():
                    connected, errors = self._connect_attempts()

            if not connected:
                return False
            self._log.debug(f"Bluetooth connected to : {self.name}")
            return True
        except (BluetoothError, Exception) as e:
            self._log.error(e)
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
            self._log.info(f"Pairing with {self.name} :: {self.mac_address}")
            try:
                self._run_command("scan on", BluetoothDevice.PRE_PAIR_SCAN)
            except BluetoothError as e:
                self._log.warning(f"Pre-pair scan failed, trying to pair anyway : {e}")
            result : list[str] = self._run_command(f"pair {self.mac_address}", agent = BluetoothDevice.AGENT, run_timeout = BluetoothDevice.PAIR_TIMEOUT)
            self._log.debug(result)
            self.refresh()
            if not self.paired:
                self._log.error(f"Pair command returned but {self.name} is not paired : {result}")
            return self.paired
        except (BluetoothError, Exception) as e:
            self._log.error(e)
            return False
        finally:
            self._pairing = False

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
