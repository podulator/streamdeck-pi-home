import subprocess
from abc import abstractmethod

class BluetoothError(Exception):
    pass

class BluetoothCtlInterface():

    COMMAND : str = "bluetoothctl"

    def __init__(self) -> None:
        pass

    def _build_args(self, command : str, timeout : int = 0, agent : str = None) -> list[str]:
        cmd_args : list[str] = [BluetoothCtlInterface.COMMAND]
        if agent:
            cmd_args.extend(["--agent", agent])
        if timeout > 0:
            cmd_args.extend(["--timeout", str(timeout)])
        cmd_args.extend(command.split())
        return cmd_args

    def _run_command(self, command : str, timeout : int = 0, agent : str = None, run_timeout : int = None) -> list[str]:
        # timeout is bluetoothctl's own --timeout, which keeps it alive for that long (needed for "scan on").
        # run_timeout only bounds the subprocess, for commands like pair/connect that exit on their own.
        cmd_args : list[str] = self._build_args(command, timeout, agent)
        p_timeout : int = run_timeout if run_timeout is not None else (None if timeout == 0 else (timeout + 2))
        try:
            process : subprocess.CompletedProcess = subprocess.run(cmd_args, text = True, capture_output = True, timeout = p_timeout)
        except subprocess.TimeoutExpired as ex:
            partial : str = ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or "")
            raise BluetoothError(f"Bluetoothctl timed out after {p_timeout}s running cmd : {' '.join(cmd_args)}\nOutput : {partial.strip()}")

        if process.returncode != 0:
            # bluetoothctl prints its errors ("Failed to pair: org.bluez.Error...") to stdout, not stderr
            err_message = "\n".join(s.strip() for s in (process.stdout, process.stderr) if s and s.strip())
            if not err_message:
                err_message = "Unknown Error"
            raise BluetoothError(f"Bluetoothctl failed after running cmd : {' '.join(cmd_args)}\nErr message : {err_message} - Err Code : ({process.returncode})")

        return process.stdout.splitlines()

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

