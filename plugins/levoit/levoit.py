import textwrap
import threading
import time

from ..IPlugin import IPlugin
from enum import Enum
from pyvesync import VeSync
from pyvesync.vesyncfan import VeSyncAirBypass, Timer
from typing import Any

class State(Enum):
	NONE = 0
	STRENGTH = 1

class Buttons(Enum):
	BACK = 0
	SPEED = 1
	MODE = 2
	ON = 3
	INFO = 4
	TIMER = 5
	DISPLAY = 6
	NIGHT_LIGHT = 7

class LevoitPlugin(IPlugin):

	POLL_SPEED : int = 60

	image_keys : list[str] = [ 
		"level-1.png", 
		"level-2.png", 
		"level-3.png", 
		"level-4.png",
		"mode-off.png", 
		"mode-sleep.png", 
		"mode-manual.png", 
		"mode-auto.png", 
		"power-on.png", 
		"power-off.png", 
		"info.png", 
		"timer.png", 
		"display-on.png",
		"display-off.png", 
		"nightlight-on.png", 
		"nightlight-off.png"
	]

	class Images(Enum):
		LEVEL_1 = 0
		LEVEL_2 = 1
		LEVEL_3 = 2
		LEVEL_4 = 3
		MODE_OFF = 4
		MODE_SLEEP = 5
		MODE_MANUAL = 6
		MODE_AUTO = 7
		POWER_ON = 8
		POWER_OFF = 9
		INFO = 10
		TIMER = 11
		DISPLAY_ON = 12
		DISPLAY_OFF = 13
		NIGHT_LIGHT_ON = 14
		NIGHT_LIGHT_OFF = 15

	def __init__(self, app, config, font) -> None:
		super().__init__(app, config, font)

		self._client : VeSync = None
		self._device : VeSyncAirBypass = None
		self._state : State = State.NONE
		self._images : list[bytes] = None
		self._thread : threading.Thread = None
		self._poll_counter : int = 0

	def _poll(self):

		self._log.info(f"{self._class} :: poll thread started :: {self._activated}")
		while self._activated:
			self._poll_counter = self._poll_counter + 1
			if self._poll_counter >= self.POLL_SPEED: 
				# possible pull out to sync func for immediate atomic actions
				if self._update_device():
					self._update_state()
			time.sleep(1)

		self._log.info(f"{self._name} :: poll thread exiting")

	def _update_device(self) -> bool:
		self._poll_counter = 0
		self._log.debug("update device")
		if self._client is not None:
			self._client.update()
			f : VeSyncAirBypass
			for f in self._client.fans:
				if f.device_name == self._config["device-name"]:
					if (self._device is None):
						self._log.debug(f"{self._class} :: found device")
					self._device = f
					return True
		return False

	def _update_screen_and_state(self):
		self._render(self.name)
		self._update_state()

	def _notify(self, message : str):
		self._poll_counter = 0
		self._render(message)
		timer = threading.Timer(5, self._update_screen_and_state)
		timer.start()

	def activate(self) -> bool:
		if not super().activate(): 
			return False

		try:
			self._activated = True
			self._render(self.name)

			if self._client is None:
				self._log.debug(f"{self._class} :: creating client")
				self._client = VeSync(
					self._config["username"], 
					self._config["password"], 
					self._config["timezone"]
				)
				if self._client.login():
					self._log.debug(f"{self._class} :: client created")
				else:
					self._log.error("Couldn't login to VeSync")
					self._notify("Couldn't login to VeSync")
					self._client = None
					self._activated = False
					return False

			if self._images is None:
				self._images = []
				self._load_images(self._images, LevoitPlugin.image_keys)

			self._state = State.NONE
			self._poll_counter = self.POLL_SPEED
			if self._thread is None:
				self._thread = threading.Thread(target = self._poll)
				self._thread.start()

		except Exception as ex:
			self._log.error(ex)
			self._activated = False

		return self._activated

	def deactivate(self):
		super().deactivate()
		if self._thread is not None:
			self._thread.join()
			self._thread = None
    
	def destroy(self):
		super().destroy()
		self.deactivate()
		self._client = None

	def run_as_daemon(self) -> None:
		pass

	def on_button_press(self, deck, key, key_state):
		super().on_button_press(deck, key, key_state)

		if not key_state: 
			return
		if self._device is None: 
			return

		match key:
			case Buttons.BACK.value:
				pass
			case Buttons.SPEED.value:
				if not self._device.is_on: 
					return
				level : int = self._device.speed
				level += 1
				if level > 4: 
					level = 1
				self._notify(f"Changing fan speed to {level}")
				self._device.change_fan_speed(level)
				self._device.details["speed"] = level
				self._update_state()

			case Buttons.MODE.value:
				# sleep, off, auto, manual
				if not self._device.is_on: 
					return
				mode : str = self._device.mode
				new_mode : str = "sleep"
				if mode == "sleep":
					new_mode  = "auto"
					self._device.auto_mode()
				elif mode == "auto":
					new_mode = "manual"
					self._device.manual_mode()
				else:
					self._device.sleep_mode()

				self._notify(f"Changing mode to {new_mode}")
				self._device.details["mode"] = new_mode
				self._device.mode = new_mode
				self._update_state()

			case Buttons.ON.value:
				if self._device.is_on:
					self._notify(f"Turning {self._name} off")
					self._device.turn_off()
					self._device.details["status"] = "off"
				else:
					self._notify(f"Turning {self._name} on")
					self._device.turn_on()
					self._device.details["status"] = "on"
				self._update_state()

			case Buttons.INFO.value:
				air_quality_level : int = self._device.details["air_quality"]
				air_quality_value : int = self._device.details["air_quality_value"]
				filter_life : int = self._device.details["filter_life"]
				msg : str = textwrap.dedent(f"""\
					Air quality : {air_quality_level}
					Air quality score : {air_quality_value}
					Filter life : {filter_life}"""
				)
				self._notify(msg)

			case Buttons.TIMER.value:
				timer : Timer = self._device.get_timer()
				msg : str = "Timer status\nNo timer set"
				if (timer is not None): 
					msg = textwrap.dedent(f"""\
						Timer status :
						Timer running : {timer.running}
						Time remaining : {timer.time_remaining}"""
					)
				self._notify(msg)

			case Buttons.DISPLAY.value:
				if not self._device.is_on: 
					return
				display : bool = self._device.details["display"]
				if (display):
					self._notify("Turning off display")
					self._device.turn_off_display()
					self._device.details["display"] = False
				else:
					self._notify("Turning on display")
					self._device.turn_on_display()
					self._device.details["display"] = True
				self._update_state()

			case Buttons.NIGHT_LIGHT.value:
				if not self._device.is_on: 
					return
				night_light : bool = self._device.details["night_light"] == "on"
				new_state : str = "off" if night_light else "on"
				msg : str = f"Turning night light {new_state}"
				self._notify(msg)
				self._device.set_night_light(new_state)
				self._device.details["night_light"] = new_state
				self._update_state()

			case _:
				pass
	
	def on_dial_turned(self, deck, dial, value):
		super().on_dial_turned(deck, dial, value)

	def _update_state(self):

		if self._device is None: 
			# speed
			self._app.set_button_image(Buttons.SPEED.value, self._images[LevoitPlugin.Images.LEVEL_1.value])
			# mode
			self._app.set_button_image(Buttons.MODE.value, self._images[LevoitPlugin.Images.MODE_OFF.value])
			# on
			self._app.set_button_image(Buttons.ON.value, self._images[LevoitPlugin.Images.POWER_OFF.value])
			# info
			self._app.set_button_image(Buttons.INFO.value, self._images[LevoitPlugin.Images.INFO.value])
			# timer
			self._app.set_button_image(Buttons.TIMER.value, self._images[LevoitPlugin.Images.TIMER.value])
			# display
			self._app.set_button_image(Buttons.DISPLAY.value, self._images[LevoitPlugin.Images.DISPLAY_OFF.value])
			# night light
			self._app.set_button_image(Buttons.NIGHT_LIGHT.value, self._images[LevoitPlugin.Images.NIGHT_LIGHT_OFF.value])
			## default message
			self._render(self.name)
			return

		self._log.debug(self._device.displayJSON())

		speed : int = self._device.speed
		display : bool = self._device.details["display"]
		night_light : bool = self._device.details["night_light"]
		# sleep, off, auto, manual
		mode : str = self._device.mode

		# speed
		match speed:
			case 1:
				self._app.set_button_image(Buttons.SPEED.value, self._images[LevoitPlugin.Images.LEVEL_1.value])
			case 2:
				self._app.set_button_image(Buttons.SPEED.value, self._images[LevoitPlugin.Images.LEVEL_2.value])
			case 3:
				self._app.set_button_image(Buttons.SPEED.value, self._images[LevoitPlugin.Images.LEVEL_3.value])
			case 4:
				self._app.set_button_image(Buttons.SPEED.value, self._images[LevoitPlugin.Images.LEVEL_4.value])

		match mode:
			case "sleep":
				self._app.set_button_image(Buttons.MODE.value, self._images[LevoitPlugin.Images.MODE_SLEEP.value])
			case "off":
				self._app.set_button_image(Buttons.MODE.value, self._images[LevoitPlugin.Images.MODE_OFF.value])
			case "auto":
				self._app.set_button_image(Buttons.MODE.value, self._images[LevoitPlugin.Images.MODE_AUTO.value])
			case "manual":
				self._app.set_button_image(Buttons.MODE.value, self._images[LevoitPlugin.Images.MODE_MANUAL.value])
			case _:
				self._log.info("unknown mode: " + mode)
				self._app.set_button_image(Buttons.MODE.value, self._images[LevoitPlugin.Images.MODE_OFF.value])

		# on
		if self._device.is_on:
			self._app.set_button_image(Buttons.ON.value, self._images[LevoitPlugin.Images.POWER_ON.value])
		else:
			self._app.set_button_image(Buttons.ON.value, self._images[LevoitPlugin.Images.POWER_OFF.value])

		# info
		self._app.set_button_image(Buttons.INFO.value, self._images[LevoitPlugin.Images.INFO.value])

		# timer
		self._app.set_button_image(Buttons.TIMER.value, self._images[LevoitPlugin.Images.TIMER.value])

		# display
		if display:
			self._app.set_button_image(Buttons.DISPLAY.value, self._images[LevoitPlugin.Images.DISPLAY_ON.value])
		else:
			self._app.set_button_image(Buttons.DISPLAY.value, self._images[LevoitPlugin.Images.DISPLAY_OFF.value])

		# night light
		night_light : bool = self._device.details["night_light"] == "on"
		if night_light:
			self._app.set_button_image(Buttons.NIGHT_LIGHT.value, self._images[LevoitPlugin.Images.NIGHT_LIGHT_ON.value])
		else:
			self._app.set_button_image(Buttons.NIGHT_LIGHT.value, self._images[LevoitPlugin.Images.NIGHT_LIGHT_OFF.value])
