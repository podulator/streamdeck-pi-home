import subprocess
from abc import abstractmethod

class BluetoothError(Exception):
    pass

class BluetoothCtlInterface():

    COMMAND : str = "bluetoothctl"

    def __init__(self) -> None:
        pass

    def _run_command(self, command : str, timeout : int = 0) -> list[str]:
        
        cmd_args : list[str] = [BluetoothCtlInterface.COMMAND]
        if timeout > 0:
            t = f"--timeout {timeout}" if timeout > 0 else ""
            cmd_args.append(t)
        cmd_args.append(command)
        cmd : str = " ".join(cmd_args)    
        p_timeout : int = None if timeout == 0 else (timeout + 2)
        process : subprocess.CompletedProcess = subprocess.run(cmd, shell = True, text = True, capture_output = True, timeout = p_timeout)
        success : bool = process.returncode == 0
        output : list[str] = process.stdout.splitlines() if success else []

        if not success:
            err_message = process.stderr
            if not err_message:
                err_message = "Unknown Error"
            raise BluetoothError(f"Bluetoothctl failed after running cmd : {cmd}\nErr message : {err_message} - Err Code : ({process.returncode})")
        else:
            return output

    def _parse_results(self, terms : list[str], lines : list[str]) -> bool:
        try:
            for l in lines:
                l = l.strip().lower()
                success : bool = all(l.find(t) != -1 for t in terms)
                if success:
                    return True
        except Exception as ex:
            raise BluetoothError(f"Failed to parse bluetoothctl output : {ex}")
        return False

    @abstractmethod
    def refresh(self) -> bool:
        pass

