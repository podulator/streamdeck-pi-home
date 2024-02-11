from abc import ABC, abstractmethod
from homekit.controller.ip_implementation import IpPairing
from homekit.model.services import ServicesTypes
from typing import Tuple
from .shared import *
from .characteristic import *

import logging
import os

class IAccessory(ABC):

    def __init__(self, id : int, name : str, pairing : IpPairing, data : dict = {}) -> None:
        self._id : int = id
        self._type : VeluxTypes = VeluxTypes.NONE
        self._name : str = name
        self._velux_name : str = ""
        self._serial_number : str = ""
        self._manufacturer : str = ""
        self._model : str = ""
        self._firmware_revision : str = ""
        self._data : dict = data
        self._characteristics : list[:ICharacteristic] = []
        self._pairing : IpPairing  = pairing
        self._log = logging.getLogger(__name__)
        self._log.setLevel(os.environ.get("LOGLEVEL", "INFO"))

    def update(self) -> bool:
        try:
            c = self.get_writeable_characteristic()
            if not c or not c.is_writeable: 
                return False
            target_value = c.get_target_value()
            current_value = c.get_current_value()

            if target_value != current_value:
                self._log.debug(f"Sending '{target_value}' to {self._id}.{c.id}")
                self._pairing.put_characteristics(
                    [(self._id, c.id, target_value)], True
                )
                return True
        except Exception as ex:
            self._log.error(ex)
            return False

    def toggle(self) -> Tuple[bool, str]:
        try:
            c : ICharacteristic = self.get_writeable_characteristic()
            if not c or not c.is_writeable: 
                return False
            value = c.get_toggle_value()
            self._log.debug(f"Sending '{value}' to {self._id}.{c.id}")
            self._pairing.put_characteristics(
                [(self._id, c.id, value)], True
            )
            return (True, f"{self._name} opening" if value != 0 else f"{self._name} closing")
        except Exception as ex:
            self._log.error(ex)
            return (False, ex)

    def get_writeable_characteristic(self) -> ICharacteristic:
        for c in self._characteristics:
            if c.is_writeable: 
                return c

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name if self._name != "" else self._velux_name if self._velux_name != "" else "Unknown"

    @property
    def serial_number(self) -> str:
        return self._serial_number

    @property
    def manufacturer(self) -> str:
        return self._manufacturer

    @property
    def model(self) -> str:
        return self._model

    @property
    def firmware_revision(self) -> str:
        return self._firmware_revision

    @property
    def data_dict(self) -> dict :
        return self._data

    @property
    def type(self) -> VeluxTypes:
        return self._type

    @property
    def characteristics(self) -> list:
        return self._characteristics

    @abstractmethod
    def get_formatted_string(self) -> str:
        pass

    def __str__(self):
        result : str = f"id : {self._id}\nname : {self._name}\nserial_number : {self._serial_number}\n"
        result += f"manufacturer : {self._manufacturer}\nmodel : {self._model}\nfirmware_revision : {self._firmware_revision}"
        return result

    def _hydrate(self, service_cb : callable):

        # https://github.com/jlusiardi/homekit_python/blob/master/homekit/model/characteristics/characteristic_types.py#L163
        for s in self._data["services"]:
            if s["iid"] == 1:
                for c in s["characteristics"]:
                    attribute_key = hex_code_from_uuid(c['type'])
                    match attribute_key:
                        case 0x23:
                            # '23': 'public.hap.characteristic.name',
                            self._velux_name = c["value"]
                        case 0x20:
                            # '20': 'public.hap.characteristic.manufacturer',
                            self._manufacturer = c["value"]
                        case 0x21:
                            # '21': 'public.hap.characteristic.model',
                            self._model = c["value"]
                        case 0x30:
                            #'30': 'public.hap.characteristic.serial-number',
                            self._serial_number = c["value"]
                        case 0x52:
                            # '52': 'public.hap.characteristic.firmware.revision', 
                            self._firmware_revision = c["value"]
                        case _:
                            #print(s_type_uuid)
                            pass
            else:
                if service_cb is not None:
                    service_cb(s)

class Gateway(IAccessory):

    def __init__(self, id : int, name : str, pairing : IpPairing, data : dict) -> None:
        super().__init__(id, name, pairing, data)
        self._type = VeluxTypes.GATEWAY
        self._version : str = ""
        super()._hydrate(self._hydrate_type)

    def _hydrate_type(self, service):
        for c in service["characteristics"]:
            attribute_key = hex_code_from_uuid(c['type'])
            match attribute_key:
                case 0x37:
                    # '37': 'public.hap.characteristic.version',
                    self.version = c["value"]
                    return
                case _:
                    pass

    @property
    def version(self) -> str:
        return self._version

    @version.setter
    def version(self, value : str):
        self._version = value

    def __str__(self):
        base = super().__str__()
        return f"{type(self)}\n{base}\nversion : {self.version}"
    
    def get_formatted_string(self) -> str:
        return f"{self.model} - serial : {self.serial_number}\nManufacturer : {self.manufacturer}\nFirmware : {self.firmware_revision}"

class Sensor(IAccessory):

    def __init__(self, id : int, name : str, pairing : IpPairing, data : dict) -> None:
        super().__init__(id, name, pairing, data)
        self._type = VeluxTypes.SENSOR
        super()._hydrate(self._hydrate_type)

    def _hydrate_type(self, service):
        s_type = hex_code_from_uuid(service["type"])
        match s_type:
            case 0x8A:
                # temperature sensor
                sensor = TemperatureSensor(service)
                self._characteristics.append(sensor)
            case 0x82:
                # humidity sensor
                sensor = HumiditySensor(service)
                self._characteristics.append(sensor)
                pass
            case 0x97:
                # carbon dioxide sensor
                sensor = CarbonDioxideSensor(service)
                self._characteristics.append(sensor)
                pass
            case _:
                self._log.debug(f"Pass on : {s_type}")

    def __str__(self):
        base = super().__str__()
        return f"{type(self)}\n{base}\n"

    def get_formatted_string(self) -> str:
        result : str = ""
        for c in self._characteristics:
            result += c.get_formatted_string() + "\n"
        return result.strip()

class ExternalCover(IAccessory):

    def __init__(self, id : int, name : str, pairing : IpPairing, data : dict) -> None:
        super().__init__(id, name, pairing, data)
        self._type = VeluxTypes.EXTERNAL_COVER
        super()._hydrate(self._hydrate_type)

    def _hydrate_type(self, service):
        s_type = hex_code_from_uuid(service["type"])
        match s_type:
            case 0x8C:
                # RollerShutter
                sensor = RollerShutter(service)
                self._characteristics.append(sensor)
            case _:
                self._log.debug(f"Pass on : {s_type}")  

    def __str__(self):
        base = super().__str__()
        return f"{type(self)}\n{base}\n"

    def get_formatted_string(self) -> str:
        result = ""
        for c in self._characteristics:
            result += c.get_formatted_string() + "\n"
        return result.strip()

class VeluxWindow(IAccessory):

    def __init__(self, id : int, name : str, pairing : IpPairing, data : dict) -> None:
        super().__init__(id, name, pairing, data)
        self._type = VeluxTypes.VELUX_WINDOW
        super()._hydrate(self._hydrate_type)
    
    def _hydrate_type(self, service):
        s_type = hex_code_from_uuid(service["type"])
        match s_type:
            case 0x8B:
                # Roof Window
                sensor = RoofWindow(service)
                self._characteristics.append(sensor)
            case _:
                self._log.debug(f"Pass on : {s_type}")  

    def __str__(self):
        base = super().__str__()
        return f"{type(self)}\n{base}\n"

    def get_formatted_string(self) -> str:
        result = ""
        for c in self._characteristics:
            result += c.get_formatted_string() + "\n"
        return result.strip()

class AccessoryFactory:

    @staticmethod
    def new(name : str, data : dict, pairing : IpPairing) -> IAccessory:
        aid = data["aid"]
        for service in data["services"]:
            s_type_uuid = service['type']
            s_type = ServicesTypes.get_short(s_type_uuid)
            match s_type:
                case "accessory-information":
                    for c in service['characteristics']:
                        if c['iid'] == 2:
                            match c["value"]:
                                case "VELUX gateway":
                                    return Gateway(aid, name, pairing, data)
                                case "VELUX Sensor":
                                    return Sensor(aid, name, pairing, data)
                                case "VELUX External Cover":
                                    return ExternalCover(aid, name, pairing, data)
                                case "VELUX Window":
                                    return VeluxWindow(aid, name, pairing, data)
                                case _:
                                    return None
                case _:
                    pass

        return None
    
    def __init__(self) -> None:
        pass
    
    def __del__(self) -> None:
        pass
