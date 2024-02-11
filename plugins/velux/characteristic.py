from .shared import *
from abc import ABC, abstractmethod, abstractproperty

import textwrap

class ICharacteristic(ABC):
    def __init__(self, type : VeluxServiceTypes) -> None:
        self._id : int = 0
        self._name : str = ""
        self._type : VeluxServiceTypes = type
        self._is_writeable : bool = False
        self._target_value : int = 0
        self._current_value : int = 0
        self._unit : str = ""
        self._min : int = 0
        self._max : int = 0
        self._state : int = 0

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def type(self) -> VeluxServiceTypes:
        return self._type

    @property
    def is_writeable(self) -> bool:
        return self._is_writeable

    @abstractmethod
    def get_formatted_string(self) -> str:
        pass

    def set_target_value(self, value : int):
        if (not self._is_writeable): return
        value = min(max(value, self._min), self._max)
        self._target_value = value

    def get_target_value(self) -> int:
        return self._target_value

    def get_current_value(self) -> int:
        return self._current_value

    def get_toggle_value(self) -> int :
        if (self.get_current_value() < (self._max / 2)):
            return self._max
        return self._min

    def _handle_unit(self, unit : str) -> str:
        match unit:
            case "celsius":
                return "°C"
            case "percentage":
                return "%"
            case _:
                return unit

    def _handle_state(self, state : int) -> str:
        match state:
            case 0:
                return "Closing"
            case 1:
                return "Opening"
            case 2:
                return "Idle"
            case _:
                return f"Unknown : {state}"

class TemperatureSensor(ICharacteristic):

    def __init__(self, data : dict) -> None:
        super().__init__(VeluxServiceTypes.TEMPERATURE_SENSOR)

        for c in data["characteristics"]:
            attribute_key = hex_code_from_uuid(c['type'])
            match attribute_key:
                case 0x23:
                    # '23': 'public.hap.characteristic.name',
                    self._name = c["value"]
                case 0x11:
                    # '11': 'public.hap.characteristic.temperature.current',
                    self._target_value = c["value"]
                    self._current_value = c["value"]
                    self._unit = c["unit"]
                case _:
                    pass

    def get_formatted_string(self) -> str:
        return f"Temperature: {self.get_target_value()} {self._handle_unit(self._unit)}"

class HumiditySensor(ICharacteristic):
    def __init__(self, data : dict) -> None:
        super().__init__(VeluxServiceTypes.HUMIDITY_SENSOR)
    
        for c in data["characteristics"]:
            attribute_key = hex_code_from_uuid(c['type'])
            match attribute_key:
                case 0x23:
                    # '23': 'public.hap.characteristic.name',
                    self._name = c["value"]
                case 0x10:
                    # '10': 'public.hap.characteristic.relative-humidity.current',
                    self._target_value = c["value"]
                    self._current_value = c["value"]
                    self._unit = c["unit"]
                case _:
                    pass

    def get_formatted_string(self) -> str:
        return f"Humidity: {self.get_target_value()} {self._handle_unit(self._unit)}"

    @property
    def writeable_data(self) -> dict:
        return super().writeable_data

class CarbonDioxideSensor(ICharacteristic):
    def __init__(self, data : dict) -> None:
        super().__init__(VeluxServiceTypes.CARBON_DIOXIDE_SENSOR)

        for c in data["characteristics"]:
            attribute_key = hex_code_from_uuid(c['type'])
            match attribute_key:
                case 0x23:
                    # '23': 'public.hap.characteristic.name',
                    self._name = c["value"]
                case 0x92:
                    # '92': 'public.hap.characteristic.carbon-dioxide.detected',
                    self._target_value = c["value"]
                    self._current_value = c["value"]
                case _:
                    pass

    def get_formatted_string(self) -> str:
        return f"CO2 level : {self.get_target_value()}"

    @property
    def writeable_data(self) -> dict:
        return super().writeable_data

class RollerShutter(ICharacteristic):
    def __init__(self, data : dict) -> None:
        super().__init__(VeluxServiceTypes.ROLLER_SHUTTER)
        self._is_writeable = True

        for c in data["characteristics"]:
            attribute_key = hex_code_from_uuid(c['type'])
            match attribute_key:
                case 0x23:
                    # '23': 'public.hap.characteristic.name',
                    self._name = c["value"]
                case 0x7C:
                    # '7C': 'public.hap.characteristic.position.target',
                    self._id = c["iid"]
                    self._target_value = c["value"]
                    self._min = c["minValue"]
                    self._max = c["maxValue"]
                    self._unit = c["unit"]
                case 0x6D:
                    # '6D': 'public.hap.characteristic.position.current',
                    self._current_value = c["value"]
                case 0x72:
                    # '72': 'public.hap.characteristic.position.state',
                    self._state =  c["value"]
                case _:
                    pass

    def get_formatted_string(self) -> str:
        return textwrap.dedent(f"""\
            Current position: {self.get_current_value()} {self._handle_unit(self._unit)}
            Target position: {self.get_target_value()} {self._handle_unit(self._unit)}
            State: {self._handle_state(self._state)}"""
        )

class RoofWindow(ICharacteristic):
    def __init__(self, data : dict) -> None:
        super().__init__(VeluxServiceTypes.ROOF_WINDOW)
        self._is_writeable = True

        for c in data["characteristics"]:
            attribute_key = hex_code_from_uuid(c['type'])
            match attribute_key:
                case 0x23:
                    # '23': 'public.hap.characteristic.name',
                    self._name = c["value"]
                case 0x7C:
                    # '7C': 'public.hap.characteristic.position.target',
                    self._id = c["iid"]
                    self._target_value = c["value"]
                    self._min = c["minValue"]
                    self._max = c["maxValue"]
                    self._unit = c["unit"]
                case 0x6D:
                    # '6D': 'public.hap.characteristic.position.current',
                    self._current_value = c["value"]
                case 0x72:
                    # '72': 'public.hap.characteristic.position.state',
                    self._state = c["value"]
                case _:
                    pass

    def get_formatted_string(self) -> str:
        return textwrap.dedent(f"""\
            Current position: {self.get_current_value()} {self._handle_unit(self._unit)}
            Target position: {self.get_target_value()} {self._handle_unit(self._unit)}
            State: {self._handle_state(self._state)}"""
        )
