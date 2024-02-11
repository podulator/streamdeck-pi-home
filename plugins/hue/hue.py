import os
import threading
import time
from ..IPlugin import IPlugin
from enum import auto, IntEnum
from phue import Bridge, Light, Scene, Group
from rgbxy import Converter
from typing import Tuple

class HuePlugin(IPlugin):

    CREDS_FILE : str = ".python_hue"

    class State(IntEnum):
        NONE = 0
        GROUPS = auto()
        LIGHTS = auto()
        SCENES = auto()
    
    class ModifierState(IntEnum):
        NONE = 0
        BRIGHTNESS = auto()
        COLOR = auto()

    class Buttons(IntEnum):
        EXIT = 0
        GROUPS = auto()
        LIGHTS = auto()
        SCENES = auto()
        SHORTCUT = auto()
        COLOR = auto()
        BRIGHTNESS = auto()
        POWER = auto()

    class ImageKeys(IntEnum):
        GROUPS = 0
        LIGHTS = auto()
        SCENES = auto()
        SHORTCUT = auto()
        COLOR = auto()
        BRIGHTNESS = auto()
        POWER_ON = auto()
        POWER_OFF = auto()
        BLANK = auto()

    FLUSH_SPEED : float = 0.3
    
    image_keys = [ 
        "group.png", 
        "lamp.png", 
        "scenes.png", 
        "shortcut.png",
        "color.png", 
        "brightness.png", 
        "on.png", 
        "off.png", 
        "blank.png"
    ]

    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)
        self._state = HuePlugin.State.NONE
        self._modifier_state : HuePlugin.ModifierState = HuePlugin.ModifierState.NONE
        self._bridge : Bridge = None
        self._converter : Converter = None

        self._group_index : int = 0
        self._light_index : int = 0
        self._scene_index : int = 0
        self._shortcut_index : int = -1

        self._images : list[bytes] = None
        self._inc_buffer : dict = {}
        self._thread : threading.Thread = None

    @property
    def config(self) -> dict:
        return self._config
    @property
    def lights(self) -> list[Light]:
        return self._bridge.lights
    @property
    def groups(self) -> list[dict]:
        return self._bridge.groups
    @property
    def scenes(self) -> list[dict]:
        return self._bridge.scenes

    def _flush(self):
        self._log.info(f"{self._class} :: flush thread started")
        while self._activated:

            brightness = self._inc_buffer.get("brightness", 0)
            hue = self._inc_buffer.get("hue", 0)
            saturation = self._inc_buffer.get("saturation", 0)

            if brightness != 0 or hue != 0 or saturation != 0:
                # reset these as fast as possible
                self._inc_buffer["brightness"] = self._inc_buffer["hue"] = self._inc_buffer["saturation"] = 0

                brightness = max(min(254, (brightness * 10)), -254)
                hue = max(min(254, (hue * 10)), -254)
                saturation = max(min(254, (saturation * 10)), -254)                    

                match self._state:
                    case HuePlugin.State.LIGHTS:
                        light : Light = self.lights[self._light_index]
                        light.brightness += brightness
                        light.hue += hue
                        light.saturation += saturation

                    case HuePlugin.State.GROUPS:
                        group : Group = self.groups[self._group_index]
                        group.brightness += brightness
                        group.hue += hue
                        group.saturation += saturation
 
                    case _:
                        pass  

            color : dict = self._inc_buffer.get("color", None)
            if color is None:
                return
            red = color.get("red", 0)
            green = color.get("green", 0)
            blue = color.get("blue", 0)

            if red != 0 or green != 0 or blue != 0:
                # reset these as fast as possible
                self._inc_buffer["color"]["red"] = self._inc_buffer["color"]["green"] = self._inc_buffer["color"]["blue"] = 0

                match self._state:
                    case HuePlugin.State.LIGHTS:
                        light : Light = self.lights[self._light_index]
                        if not hasattr(light, "rgb"): 
                            return

                        light.rgb = [
                            max(min(255, light.rgb[0] + red), 0), 
                            max(min(255, light.rgb[1] + green), 0), 
                            max(min(255, light.rgb[2] + blue), 0)
                        ]

                        light.xy = self._converter.rgb_to_xy(
                            light.rgb[0], 
                            light.rgb[1], 
                            light.rgb[2])

                        pass
                    case _:
                        pass

            time.sleep(self.FLUSH_SPEED)

        self._log.info(f"{self._class} :: flush thread exiting")

    def activate(self) -> bool:
        if not super().activate(): 
            return False
        try:

            if self._bridge is None:

                creds_path : str = os.path.join(self._app.creds_path, self.CREDS_FILE)
                ip : str = self._config.get("ip", None)
                self._bridge = Bridge(ip = ip, config_file_path = creds_path)

            self._bridge.connect()
            self._render(self.name)
            self._converter = Converter()

            if self._images is None:
                self._images = []
                self._load_images(self._images, HuePlugin.image_keys)

            self._reset_state()
            self._update_buttons()

            for l in self.lights:
                try:
                    rgb : Tuple[int, int, int] = self._converter.xy_to_rgb(l.xy[0], l.xy[1])
                    l.rgb = rgb
                except KeyError as ex:
                    pass

            if self._thread is None:
                self._thread = threading.Thread(target = self._flush, daemon = True)
                self._thread.start()

        except Exception as ex:
            self._log.error(ex)
            self._activated = False

        return self._activated

    def deactivate(self):
        super().deactivate()
        try:
            if (self._thread):
                self._thread.join()
                self._thread = None
        except:
            pass
    
    def destroy(self):
        super().destroy()
        self.deactivate()

    def run_as_daemon(self) -> None:
        pass

    def _reset_state(self) -> None:
        self._state = HuePlugin.State.NONE
        self._group_index = 0
        self._light_index = 0
        self._scene_index = 0
        self._reset_buffers()

    def _reset_buffers(self) -> None:
        self._inc_buffer = {
            "brightness": 0, 
            "hue": 0, 
            "saturation": 0,
            "color": {
                "red": 0, 
                "green": 0,
                "blue": 0
            }
        }

    def _update_buttons(self):

        self._app.set_button_image(HuePlugin.Buttons.EXIT, self._app.home_image)
        self._app.set_button_image(HuePlugin.Buttons.GROUPS, self._images[HuePlugin.ImageKeys.GROUPS])
        self._app.set_button_image(HuePlugin.Buttons.LIGHTS, self._images[HuePlugin.ImageKeys.LIGHTS])
        self._app.set_button_image(HuePlugin.Buttons.SCENES, self._images[HuePlugin.ImageKeys.SCENES])
        self._app.set_button_image(HuePlugin.Buttons.SHORTCUT, self._images[HuePlugin.ImageKeys.SHORTCUT])
        
        self._app.set_button_image(HuePlugin.Buttons.COLOR, )
        self._app.set_button_image(HuePlugin.Buttons.BRIGHTNESS, self._images[HuePlugin.ImageKeys.BRIGHTNESS])

        power : bytes = None
        color : bytes = None

        match self._state:
            case HuePlugin.State.GROUPS:
                group : Group = self.groups[self._group_index]
                power = self._images[HuePlugin.ImageKeys.POWER_ON] if group.on else self._images[HuePlugin.ImageKeys.POWER_OFF]
                color = self._images[HuePlugin.ImageKeys.COLOR]
            case HuePlugin.State.LIGHTS:
                light : Light = self.lights[self._light_index]
                color = self._images[HuePlugin.ImageKeys.COLOR] if hasattr(light, "rgb") else self._images[HuePlugin.ImageKeys.BLANK]
                power = self._images[HuePlugin.ImageKeys.POWER_ON] if light.on else self._images[HuePlugin.ImageKeys.POWER_OFF]
            case _:
                power = self._images[HuePlugin.ImageKeys.BLANK]
                color = self._images[HuePlugin.ImageKeys.COLOR]

        self._app.set_button_image(HuePlugin.Buttons.COLOR, color)
        self._app.set_button_image(HuePlugin.Buttons.POWER, power)

    def _show_groups(self):
        current_group : Group = self.groups[self._group_index]
        self._update_buttons()
        self._render(f"Group\n:- {current_group.name}")

    def _show_lights(self):
        current_light : Light = self.lights[self._light_index]
        self._update_buttons()
        self._render(f"Light\n:- {current_light.name}")

    def _show_scenes(self):
        current_scene : Scene = self.scenes[self._scene_index]
        group : Group = self.groups[int(current_scene.group)]
        self._update_buttons()
        self._render(f"Scene\n:- {current_scene.name}\n  :- Group :: ({group.name})")
    
    def _switch_group(self, group : Group) -> None:
        if group.on:
            self._log.info(f"Turning group {group.name} off")
        else:
            self._log.info(f"Turning group {group.name} on")
        group.on = not group.on
        self._update_buttons()

    def _switch_light(self, light : Light) -> None:
        if light.on:
            self._log.info(f"Turning light {light.name} off")
        else:
            self._log.info(f"Turning light {light.name} on")
        light.on = not light.on
        self._update_buttons()

    def _apply_scene(self, scene : Scene, group : Group) -> None:
        try:
            self._log.info(f"Applying scene {scene.name} to group {group.name}")
            self._bridge.run_scene(group.name, scene.name)
        except Exception as ex:
            self._log.error(ex)
            pass

    def on_button_press(self, deck, key, key_state):
        super().on_button_press(deck, key, key_state)

        if not key_state: 
            return

        match key:
            case HuePlugin.Buttons.GROUPS:
                self._reset_state()
                self._state = HuePlugin.State.GROUPS
                self._show_groups()
            case HuePlugin.Buttons.LIGHTS:
                self._reset_state()
                self._state = HuePlugin.State.LIGHTS
                self._show_lights()
            case HuePlugin.Buttons.SCENES:
                self._reset_state()
                self._state = HuePlugin.State.SCENES
                self._show_scenes()
            case HuePlugin.Buttons.SHORTCUT:
                shortcut = self._config.get("shortcut", None)
                if shortcut:
                    shortcut_group : str = shortcut.get("group", None)
                    shortcut_scenes : list[str] = shortcut.get("scenes", None)
                    if shortcut_group and shortcut_scenes:
                        shortcut_group = shortcut_group.lower()
                        groups : list[Group] = [x for x in self.groups if x.name.lower() == shortcut_group]
                        if len(groups) == 0:
                            return
                        g : Group = groups[0]
                        num_scenes : int = len(shortcut_scenes)
                        self._shortcut_index = (self._shortcut_index + 1) % num_scenes
                        this_scene : str = shortcut_scenes[self._shortcut_index].lower()
                        this_group_id : str = str(g.group_id)
                        potential_scenes : list[Scene] = [x for x in self.scenes if (x.name.lower() == this_scene and x.group == this_group_id)]
                        if len(potential_scenes) == 0:
                            return
                        s = potential_scenes[0]
                        self._apply_scene(s, g)

            case HuePlugin.Buttons.COLOR:
                self._modifier_state = HuePlugin.ModifierState.COLOR
                match self._state:
                    case HuePlugin.State.LIGHTS:
                        # reset the color buffer to zero
                        self._reset_buffers()
                        light : Light = self.lights[self._light_index]
                        if hasattr(light, "rgb"):
                            self._render(
                                f"Color\nLight :: {light.name}\n1.) N/A     2.) Red    3.) Green  4.) Blue"
                            )
                        else:
                            self._render(f"Color\nLight :: {light.name}\nDoes not support color changes")
                            pass
                        pass
                    case _:
                        self._render("Color only works on lights")
                        pass

            case HuePlugin.Buttons.BRIGHTNESS:
                self._modifier_state = HuePlugin.ModifierState.BRIGHTNESS
                match self._state:
                    case HuePlugin.State.LIGHTS:
                        self._reset_buffers()
                        light : Light = self.lights[self._light_index]
                        self._render(
                            f"Brightness\nLight :: {light.name}\n1.) N/A    2.) Bright   3.) Hue    4.) Sat"
                        )
                        pass
                    case HuePlugin.State.GROUPS:
                        self._reset_buffers()
                        group : Group = self.groups[self._group_index]
                        self._render(
                            f"Brightness\nGroup :: {group.name}\n1.) N/A    2.) Bright   3.) Hue    4.) Sat"
                        )
                        pass
                    case _:
                        pass
                pass
            case HuePlugin.Buttons.POWER:
                match self._state:
                    case HuePlugin.State.GROUPS:
                        self._switch_group(self.groups[self._group_index])
                    case HuePlugin.State.LIGHTS:
                        self._switch_light(self.lights[self._light_index])
                        pass
                    case _:
                        pass
            case _:
                pass

    def on_dial_turned(self, deck, dial, value):
        super().on_dial_turned(deck, dial, value)

        match dial:
            case 0:
                match self._state:
                    case HuePlugin.State.GROUPS:
                        self._group_index += sorted((-1, value, 1))[1]
                        self._group_index = self._wrap(self._group_index, len(self.groups))
                        self._show_groups()
                    case HuePlugin.State.LIGHTS:
                        self._light_index += sorted((-1, value, 1))[1]
                        self._light_index = self._wrap(self._light_index, len(self.lights))
                        self._show_lights()
                    case HuePlugin.State.SCENES:
                        self._scene_index += sorted((-1, value, 1))[1]
                        self._scene_index = self._wrap(self._scene_index, len(self.scenes))
                        self._show_scenes()
                    case _:
                        pass
            case _:
                match self._modifier_state:
                    case HuePlugin.ModifierState.COLOR:
                        light : Light = self.lights[self._light_index]
                        if not hasattr(light, "rgb"):
                            return
                        match dial:
                            case 1:
                                self._inc_buffer["color"]["red"] += value
                            case 2:
                                self._inc_buffer["color"]["green"] += value
                            case 3:
                                self._inc_buffer["color"]["blue"] += value
                            case _:
                                pass
                    case HuePlugin.ModifierState.BRIGHTNESS:
                        match dial:
                            case 1:
                                self._inc_buffer["brightness"] += value
                            case 2:
                                self._inc_buffer["hue"] += value
                            case 3:
                                self._inc_buffer["saturation"] += value
                            case _:
                                pass
                    case _:
                        pass

    def on_dial_pushed(self, deck, dial, state):
        super().on_dial_pushed(deck, dial, state)
    
        if not state: 
            return

        match self._state:
            case HuePlugin.State.SCENES:
                if dial == 0:
                    try:
                        scene : Scene = self.scenes[self._scene_index]
                        group : Group = self.groups[int(scene.group)]
                        self._apply_scene(scene, group)
                    except Exception as ex:
                        self._log.error(ex)
            case _:
                return
