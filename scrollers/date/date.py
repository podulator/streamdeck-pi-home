from typing import Dict, Any, Optional
from ..IScroller import IScroller
from datetime import datetime

class DateScroller(IScroller):
    """
    A subclass of the IScroller class that generates a scroller with the current date and time.
    """

    def __init__(self, app: Any, config: Dict[str, Any], font: Optional[str] = None) -> None:
        """
        Initializes the DateScroller instance.

        Args:
        """
        super().__init__(app, config, font)

    def generate(self) -> bytes:
        """
        Generates the scroller with the current date and time.

        Returns:
            bytes: The generated scroller as bytes.
        """
        try:
            today = datetime.today().strftime(self._config["format"])
            return self._render(today)
        except Exception as ex:
            # Handle the exception here, e.g. log the error or return a default image
            self._log.error(ex)
            return None

    def deactivate(self) -> None:
        """
        Deactivates the scroller.
        """
        super().deactivate()
