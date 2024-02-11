from ..IScroller import IScroller
import os
import subprocess

class CmdScroller(IScroller):
    """
    Subclass of IScroller that executes a command and retrieves the output.
    """

    def __init__(self, app: str, config: dict, font: str) -> None:
        super().__init__(app, config, font)

    def generate(self) -> bytes:
        """
        Executes a command using subprocess.Popen and retrieves the output.
        Cleans the output and passes it to the _render method for rendering.
        Returns the rendered output as bytes.
        """
        rendered_output : bytes = None
        try:
            command : str = self._config.get("command", False)
            if not command:
                raise ValueError("Command not found in config.")
            output : str = self._execute_command(command)
            cleaned_output : str = self._clean_output(output)
            template : str = self._config.get("template", "{}")
            rendered_output = self._render(template.format(cleaned_output))
        except:
            pass
        return rendered_output

    def deactivate(self) -> None:
        """
        Empty method that does nothing.
        """
        pass

    def _execute_command(self, command: str) -> str:
        """
        Executes the given command and returns the output as a string.
        """
        process = subprocess.Popen(
            command,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            shell = True
        )
        stdout, _ = process.communicate()
        return stdout.decode('utf-8')

    def _clean_output(self, output: str) -> str:
        """
        Cleans the output by removing empty lines and leading/trailing whitespace.
        Returns the cleaned output as a string, joining a list[str] on \n
        """
        lines : str[list] = output.split(os.linesep)
        cleaned_lines : list[str] = [line.strip() for line in lines if line.strip()]
        return os.linesep.join(cleaned_lines)
