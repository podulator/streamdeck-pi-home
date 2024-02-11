from enum import Enum

def hex_code_from_uuid(uuid : str) -> int:
    """ takes a full uuid and extracts the hex code and returns it as an int"""
    return int(uuid.split("-")[0], 16)

class VeluxTypes(Enum):
    NONE = 0
    GATEWAY = 1
    SENSOR = 2
    EXTERNAL_COVER = 3
    VELUX_WINDOW = 4

class VeluxServiceTypes(Enum):
    NONE = 0
    TEMPERATURE_SENSOR = 1
    HUMIDITY_SENSOR = 2
    CARBON_DIOXIDE_SENSOR = 3
    ROLLER_SHUTTER = 4
    ROOF_WINDOW = 5
