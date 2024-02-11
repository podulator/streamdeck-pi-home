from ..IScroller import IScroller
from datetime import datetime

class ClockScroller(IScroller):
    
    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)
    
    def generate(self) -> bytes:
        return self._render(datetime.now().strftime(self._config["format"]))

    def deactivate(self):
        pass
