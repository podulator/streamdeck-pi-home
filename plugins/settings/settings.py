from ..IPlugin import IPlugin
from enum import IntEnum
import os
import subprocess
import sys
import threading

class SettingsPlugin(IPlugin):

	class Buttons(IntEnum):
		EXIT = 0
		UPDATE = 1
		REBOOT = 2
		POWER_OFF = 3
		INFO = 4
		RELOAD = 5
		SAVE = 6
		BLANK_1 = 7

	image_keys = [ 
		"update.png", 
		"reboot.png", 
		"power-off.png", 
		"info.png", 
		"reload.png", 
		"save.png", 
		"blank.png" 
	]

	def __init__(self, app, config, font) -> None:
		super().__init__(app, config, font)
		self._images : list[bytes] = None

	def activate(self) -> bool:
		try:
			if not super().activate(): 
				return False

			if self._images is None:
				self._images = []
				self._load_images(self._images, self.image_keys)

			self._app.set_button_image(SettingsPlugin.Buttons.UPDATE, self._images[0])
			self._app.set_button_image(SettingsPlugin.Buttons.REBOOT, self._images[1])
			self._app.set_button_image(SettingsPlugin.Buttons.POWER_OFF, self._images[2])
			self._app.set_button_image(SettingsPlugin.Buttons.INFO, self._images[3])
			self._app.set_button_image(SettingsPlugin.Buttons.RELOAD, self._images[4])
			self._app.set_button_image(SettingsPlugin.Buttons.SAVE, self._images[5])
			self._app.set_button_image(SettingsPlugin.Buttons.BLANK_1, self._images[6])
			self._update_state()
			self._activated = True
		except Exception as ex:
			self._log.error(ex)

		return self._activated

	def deactivate(self):
		super().deactivate()
    
	def destroy(self):
		super().destroy()

	def run_as_daemon(self) -> None:
		pass

	def on_button_press(self, deck, key, key_state):
		super().on_button_press(deck, key, key_state)

		if not key_state: 
			return

		match key:
			case SettingsPlugin.Buttons.EXIT:
				pass
			case SettingsPlugin.Buttons.UPDATE:
				self._log.debug("update button pressed")
				self._run_update()
			case SettingsPlugin.Buttons.REBOOT:
				self._log.debug("reboot button pressed")
				self._run_reboot()
			case SettingsPlugin.Buttons.POWER_OFF:
				self._log.debug("power off button pressed")
				self._run_power_off()
			case SettingsPlugin.Buttons.INFO:
				self._log.debug("info button pressed")
				self._run_info()
			case SettingsPlugin.Buttons.RELOAD:
				self._log.debug("reload button pressed")
				self._run_reload()
			case SettingsPlugin.Buttons.SAVE:
				self._log.debug("save button pressed")
				self._notify("Saving...\nPlease wait...", True)
				self._app.save_config()
				self._update_state()
			case _:
				self._log.debug("unknown button pressed")
				return

	def on_dial_turned(self, deck, dial, value):
		super().on_dial_turned(deck, dial, value)

	def _update_state(self):
		self._render("Settings", self._font["font_size"])

	def _run_reload(self):
		try:
			self._notify("Reloading...\nPlease wait...", True)
			self._app.destroy()
		except:
			pass
		sys.exit(0)

	def _run_info(self):
		command = self._get_command_by_name("info")
		result = self._command_runner(command)
		self._log.debug(result)
		self._notify(f"{result}", True)

	def _run_power_off(self):
		self._notify("Powering off...\nPlease wait...", True)
		command = self._get_command_by_name("shutdown")
		result = self._command_runner(command)
		self._log.debug(result)
		self._notify(f"Power off: \n{result}", False)

	def _run_reboot(self):
		self._notify("Rebooting...\nPlease wait...", True)
		command = self._get_command_by_name("reboot")
		result = self._command_runner(command)
		self._log.debug(result)
		self._notify(f"Reboot: \n{result}", False)

	def _run_update(self):
		self._notify("Updating...\nPlease wait...", True)
		command = self._get_command_by_name("update")
		result = self._command_runner(command)
		self._log.debug(result)
		self._notify(f"Update: \n{result}", False)

	def _get_command_by_name(self, name) -> dict:
		for command in self._config["commands"]:
			if command["name"] == name:
				return command
		return None

	def _command_runner(self, command : dict) -> str:

		cmd = command.get("command", None)
		template = command.get("template", None)
		if not cmd or not template:
			return "No command or template"

		result = subprocess.run(
			cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			shell=True,
			encoding='utf-8'
		)
		cleaned : str = [line.strip() for line in result.stdout.split(os.linesep) if line.strip()]
		match result.returncode:
			case 0:
				if not cleaned:
					return template.format("Great success!")
				return os.linesep.join(cleaned)
			case _:
				return f"Returned {result.returncode}"

	def _notify(self, message : str, keep : bool = False):
		self._render(message, self._font["font_size"])
		if not keep:
			timer = threading.Timer(5.0, self._update_state)
			timer.start()
