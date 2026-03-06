import logging
import tinytuya

from enum import IntEnum

class VacuumDevice(tinytuya.Device):

    log = logging.getLogger(__name__)

    ## pulled from devices.json Mapping section
    class _VacuumParams(IntEnum):
        POWER=1
        POWER_GO=2
        MODE=3
        DIRECTION_CONTROL=4
        STATUS=5
        ELECTRICITY_LEFT=6
        EDGE_BRUSH=7
        ROLL_BRUSH=8
        FILTER=9
        RESET_EDGE_BRUSH=10
        RESET_ROLL_BRUSH=11
        RESET_FILTER=12
        SEEK=13
        SUCTION=14
        CLEAN_TIME=17
        FAULT=18
        CISTERN=20
        DUSTER_CLOTH=21
        RESET_DUSTER_CLOTH=22

    class _VacuumModes(IntEnum):
        STANDBY=1
        RANDOM=2
        WALL_FOLLOW=3
        SPIRAL=4
        CHARGEGO=5

    def clean(self, nowait=False) -> void:
        self.log.debug("Cleaning requested")
        self.set_value(self._VacuumParams.MODE, "random", nowait=nowait)
        self.set_status(True, int(self._VacuumParams.POWER_GO), nowait=nowait)

    def pause(self, nowait=False) -> void:
        self.log.debug("Pause requested")
        self.set_value(self._VacuumParams.MODE, "standby", nowait=nowait)
        self.set_status(False, int(self._VacuumParams.POWER_GO), nowait=nowait)

    def charge(self, nowait=False) -> void:
        self.log.debug("Charge requested")
        data = self.status()
        if not data[str(self._VacuumParams.POWER_GO.name)]:
            print("Setting powergo on")
            self.set_status(True, int(self._VacuumParams.POWER_GO), nowait=nowait)
        self.set_value(self._VacuumParams.MODE, "chargego", nowait=nowait)

    def status(self, nowait=False):
        result = {}
        try:
            data = super().status(nowait=nowait)["dps"]
            for key in data.keys():
                key_name = f"{self._VacuumParams(int(key)).name}"
                result[key_name] = data[key]
        except Exception as ex:
            self.log.error(ex)
        return result
