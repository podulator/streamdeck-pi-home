from .accessory import *

class VeluxZone():
    def __init__(self, name : str) -> None:
        self._name : str = name
        self._accessories : list[:IAccessory] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def accessories(self) -> list[:IAccessory]:
        return self._accessories

    @accessories.setter
    def accessories(self, value : list[:IAccessory]):
        self._accessories = value