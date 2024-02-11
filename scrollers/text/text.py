from ..IScroller import IScroller

class TextScroller(IScroller):
    
    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)
        self._pages = [line for line in self._config["lines"]]

    def generate(self) -> bytes:
        self._page_counter = 0
        if self.has_next:
            return self.next()
        return None

    def deactivate(self):
        super().deactivate()
