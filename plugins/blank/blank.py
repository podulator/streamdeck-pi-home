from ..IPlugin import IPlugin

class BlankPlugin(IPlugin):

	image_keys :list[str] = []

	def __init__(self, app, config, font) -> None:
		super().__init__(app, config, font)

	def activate(self) -> bool:
		return False

	def deactivate(self):
		super().deactivate()
    
	def destroy(self):
		super().destroy()

	def run_as_daemon(self) -> None:
		pass

	def on_button_press(self, deck, key, key_state):
		super().on_button_press(deck, key, key_state)

	def on_dial_turned(self, deck, dial, value):
		super().on_dial_turned(deck, dial, value)
