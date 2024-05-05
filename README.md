# streamdeck-pi-home

StreamDeck + home interface, using plugins to control Navidrome Audio, Tado heating, Hue lights, Fire TV etc. 
Also provides simple info from a number of sources in Home mode, via the Scrollers.

The idea of the project it to bang an Orange Pi Zero 2W onto the StreamDeck + and control everything with dials, buttons and knobs, like nature intended :) 

I'm open to writing extra plugins etc on demand, if anyone spots this, depending on hardware requirements / access etc. 

## Home state

Primary buttons are populated via the config `Plugins` section. 
The screen shows content from the `Scrollers` section of the config, rotated every 15 seconds.
The screen automatically dims slowly with no inputs registered, 10% every minute, in the Home layout.

**Dials**

- 1 : N/A
- 2 : N/A
- 3 : Scroll through the Scrollers manually. Does not go through the sub pages, only the inital page for each scroller.
- 4 : Controls screen brightness manually. 
  - Push to toggle between 100% and 10%.
  - Turn to move incrementally.

**Buttons** 

Pressing any primary button with an Icon takes you to that plugin. 
Pressing the 1st (Home) button resets everything. 

## Plugins

Plugins are custom written, following [a simple interface](plugins/IPlugin.py).
They have an activate / deactivate lifecycle, and so can keep their data between uses. 

They are accessed from the Home page main buttons. 
Upon entry, they provide their own layout, and always a 'Back' button in the first slot, to return Home. 
After that, their behaviour is custom. 

### Plugin : Blank

Because we're all part of the blank generation ;) 

Just used to do a NOOP and set a nice button where there is nothing happening

### Plugin : Bluetooth

Scans your environment, and builds a list of connectable devices. 

Auto connects to the saved connection on startup, so you can jump straight into playing music via Jellyfin. 

**Supported**

- Button 1 - Home
- Button 2 - Connect to a device.
  - Press to enter select mode.
  - Use dial 1 to select the device you want to connect to. 
  - Press the dial 1 again to 
    - disconnect from any current connections
    - connect to the new endpoint
- Button 3 - Scan for devices.
- Button 4 - Toggle bluetooth device power on and off.
- Button 5 - Forget an endpoint. 
  - Press to enter select mode.
  - Use dial 1 to select the device you want to forget. 
  - Press the dial 1 again to carry out the forget action
- Button 6 - Show info about self.
- Button 7 - Toggle auto connect on and off.
- Button 8 - N/A

### Plugin : Fire TV

Controls your Fire TV. 
Requires `adb debugging` to be enabled. 
On first run of the plugin it will need you to approve the connection, but then it will generate pub / pri key pair. 


**Supported**

- Media Controls
- Live TV control
- Shortcut launching
  - You can configure this throught he Fire TV ui. I use it for Input switching.
- Package launching
  - Browse and launch all 3rd party installed Packages.
  - Create favourites for quick launching.
- Power On / Off
- Alexa invoking

**Environment Variables**

```
STREAMDECK_FIRE_TV_IP="your fire cube or tv ip address"
STREAMDECK_FIRE_TV_PORT="5555"
```

**Dials**

- Dial 1 -> In package browser, push to launch selected package.
- Dial 2 -> Rotate to adjust volume, click to go Home.
- Dial 3 -> Rotate to navigate Up and Down, click to go Back.
- Dial 4 -> Rotate to go Left and Right, click to Select.

### Plugin : Hue lights

Manages connection and credentials for you on first run. Make sure you press the Hub action button with half a minute before first activation. 

Indexes your Groups, Scenes and individual lights on 1st Activate. 

**Supported**

- Groups On / Off.
- Individual lights On / Off.
- 1st Dial selects group, light or scene, depending on mode.
  - Press to activate scene.
- Brightness, Hue and Saturation for device and group are supported.
- RGB color for single lights is supported.
- Toggle between 2 scenes is supported, ie Film Night and Default.

**Environment Variables**

```
STREAMDECK_HUE_IP="the location of youe Hue hub"
```

### Plugin : Jellyfin Audio Client

Pretty feature rich media player interface for your Jellyfin Music collection. 

It's built around python-vlc.

**Supported**

- Button 1 - Home.
- Button 2 - Tree traversal of collection via dial 1 rotation. 
  - Starts with A-Z + 0 partitions. Click Dial to enter. 
  - Artists that start with partition letter. Click dial to enter. Icon changes.
  - Albums by selected artist. Dial 1 rotation selects. Click dial 1 to enter. Icon changes.
  - Tracks for selected album. Dial 1 rotation selects. Click dial 1 to add to playlist. Icon changes.
  - Button 1 takes you back up a level at any time.
- Button 3 - Playlist loop On / Off.
- Button 4 - Shuffle playlist. Simple click.
- Button 5 - Add to playlist. Simple click. Adds whole album if you are at album depth, or current track in track select depth.
- Button 6 - Stop. Simple click. Subsequent play will begin from next track in playlist.
- Button 7 - Play / Pause toggle. Icon changes. 
- Button 8 - Next. Simple click. Advances to next track in playlist. 

**Dials**

- Dial 1 -> Artist / Album / Track selector
- Dial 2 -> One click extra functionality selector. Press dial to enact.
  - Show current track name.
  - Show next playlist track name.
  - Toggle Info latch. 
    - Basically, do you want to keep the current playing track name displayed, or go back to the Artist / Album / Track selector on track change.
  - Clear playlist.
  - Clear cache -> useful if your Jellyfin has re-indexed your collection.
- Dial 3 -> Playlist management
  - Scroll through current playlist
  - Press dial to activate, scroll through playlist, press dial to remove selected entry.
  - Use dial 2 to bring up the current playing track again afterwards.
- Dial 4 -> Volume Up / Down, push t toggle mute

**Environment Variables**

```
STREAMDECK_JELLYFIN_USERNAME="your jellyfin profile username"
STREAMDECK_JELLYFIN_PASSWORD="the matching profile password"
STREAMDECK_JELLYFIN_IP="http://your jellyfin server address:port"
```

### Plugin : Levoit Core 400S Air Purifier

Full control of your Levoit Core 400S Air Purifier via the VeSync account and library.

**Supported**

- Button 1 - Home
- Button 2 - Speed control, 1 - 4. Each press cycles to next strength.
- Button 3 - Night Light On / Off.
- Button 4 - Power On / Off.
- Button 5 - Info about the device.
- Button 6 - Any info about the timer.
- Button 7 - Display On / Off.
- Button 8 - Sleep mode On / Off.

**Environment Variables**

```
STREAMDECK_VESYNC_USERNAME="your VeSync account email address"
STREAMDECK_VESYNC_PASSWORD="your VeSync account password"
STREAMDECK_VESYNC_TIMEZONE="Timezone like Europe/Berlin"
```

### Plugin : Internet Radio

A simple internet radio selector and streamer. 
Provides shortcut quick launch buttons for the first 3 defined stations, and then lets you scroll and click to play for the rest. 

**Supported**

- Button 1 - Home.
- Button 2 - Play station one.
- Button 3 - Play station two.
- Button 4 - Play station three.
- Button 5 - Play the station before this one.
- Button 6 - Stop playing, and clear the current station.
- Button 7 - Pause/ Play toggle.
- Button 8 - Play the station after this one.

**Dials**

- Dial 1 -> Rotate to select a station, and click to play.
- Dial 2 -> N/A
- Dial 3 -> N/A
- Dial 4 -> N/A

### Plugin : Settings

Some basic settings 

**Supported**

- Button 1 - Home.
- Button 2 - Update to latest git commit. (Requires git cli installed)
- Button 3 - Reboot the machine.
- Button 4 - Power off the machine.
- Button 5 - Info about current version.
- Button 6 - Reload the app.
- Button 7 - Save Settings. (Updates Bluetooth auto connect flag and device)
- Button 8 - N/A. 

### Plugin : Subsonic Audio Client

Audio client for Navidrome and all subsonic compatible API's. 


**Supported**

- Button 1 - Home.
- Button 2 - Tree traversal of collection via dial 1 rotation. 
  - Starts with A-Z + 0 partitions. Click Dial to enter. 
  - Artists that start with partition letter. Click dial to enter. Icon changes.
  - Albums by selected artist. Dial 1 rotation selects. Click dial 1 to enter. Icon changes.
  - Tracks for selected album. Dial 1 rotation selects. Click dial 1 to add to playlist. Icon changes.
  - Button 1 takes you back up a level at any time.
- Button 3 - Playlist loop On / Off.
- Button 4 - Shuffle playlist. Simple click.
- Button 5 - Add to playlist. Simple click. Adds whole album if you are at album depth, or current track in track select depth.
- Button 6 - Stop. Simple click. Subsequent play will begin from next track in playlist.
- Button 7 - Play / Pause toggle. Icon changes. 
- Button 8 - Next. Simple click. Advances to next track in playlist. 

**Dials**

- Dial 1 -> Artist / Album / Track selector
- Dial 2 -> One click extra functionality selector. Press dial to enact.
  - Show current track name.
  - Show next playlist track name.
  - Toggle Info latch. 
    - Basically, do you want to keep the current playing track name displayed, or go back to the Artist / Album / Track selector on track change.
  - Clear playlist.
  - Clear cache -> useful if your Jellyfin has re-indexed your collection.
- Dial 3 -> Playlist management
  - Scroll through current playlist
  - Press dial to activate, scroll through playlist, press dial to remove selected entry.
  - Use dial 2 to bring up the current playing track again afterwards.
- Dial 4 -> Volume Up / Down, push t toggle mute


**Environment Variables**

```
STREAMDECK_SUBSONIC_USERNAME="your subsonic profile username"
STREAMDECK_SUBSONIC_PASSWORD="the matching profile password"
STREAMDECK_SUBSONIC_IP="http://your subsonic server address"
STREAMDECK_SUBSONIC_PORT="4533"
```

### Plugin : Tado Heating

Controls Tado smart radiator valves, at the device or room level. 

Scans your zones and devices on 1st Activate. 
It then lets you tweak the heating in any zone, and turn it on or off.
The plugin also exposes the weather functionality, and let's you change the Home / Away setting.

**Actions**

Buttons drive the top level functions, in order :: 

- Zones
  - 1st dial scrolls. Click enters. 2nd dial selects desired temperature. 2nd dial click sets.
- Devices
  - 1st dial scrolls through devices
- Heating On
- Toggle Home / Away
- Weather
- Stats (TODO)
- Heating Off

**Environment Variables**

```
STREAMDECK_TADO_USERNAME="your tado account email address"
STREAMDECK_TADO_PASSWORD="your tado account password"
```

### Plugin : Velux KIX300

Plugin to view and manage your Velux Accessories. 

Currently supports 
- Gateway
- Sensor
  - Temperature
  - Humidity
  - CO2 levels
- External shutters
- Windows

You will need to pair to your hub, discover devices and write a pairing file, as per [this link](https://github.com/jlusiardi/homekit_python#installation), as it is built on the homekit stack. 
Put the file in the `.creds` folder to keep it out of version control, and just add the filename to our config file.

**Supported**

- Button 1 - Home
- Button 2 - Toggle info about the Gateway device.
- Button 3 - Toggle Sensor select mode.
  - Rotate dial one to select the Sensor you are interested in.
  - Press dial one to show info from your Sensor.
- Button 4 - Toggle Zone select mode.
  - Rotate dial one to select the Zone you are interested in.
  - Press dial one to select the Zone, and enter Accessory selection mode. 
  - Rotate dial one to select your Accessory.
  - Press dial one to show info from your Accessory.
  - Rotate dial two to adjust the target value.
  - Press dial two to apply the new target value.
  - Press dial three to toggle the accesories state.
- Button 5 - Toggle Shutters mode.
  - Rotate dial one to select your Shutter.
  - Press dial one to show info about your Shutter.
  - Rotate dial two to adjust the target value.
  - Press dial two to apply the new target value.
  - Press dial three to Open or Close the shutter.
- Button 6 - Toggle Windows mode.
  - Rotate dial one to select your Window.
  - Press dial one to show info about your Window.
  - Rotate dial two to adjust the target value.
  - Press dial two to apply the new target value.
  - Press dial three to Open or Close the window.
- Button 7 - N/A.
- Button 8 - N/A.

## Homepage Scrollers

Scrollers are custom written, following [a simple interface](scrollers/IScroller.py).

Scrollers are shown on the display screen when no plugin is being used. 
They cycle periodically and essentially provide text info, and an icon for the scroller type.
Currently, we've got the following available. 


| Name    | Class   | Config opts                            | Description                                                                            |
|---------|---------|----------------------------------------|----------------------------------------------------------------------------------------|
| Clock   | clock   | format                                 | Provides a simple clock based on a format from our config                              |
| Command | cmd     | command, template                      | A command line runner and a template to present the result                             |
| Date    | date    | format                                 | Provides a simple date display based on a format from our config                       |
| Stocks  | stocks  | symbols[{name, symbol}]                | list[{name, symbol}] of the stocks we want to show                                     |
| Text    | text    | lines[str]                             | Displays a fixed message, one line at a time                                           |
| Weather | weather | mode,  location,  latitude,  longitude | Shows either the weather today, or now, configured by mode, across a number of screens |

Weather is provided by the [open meteo api](https://api.open-meteo.com/v1/forecast), and is cached for 120 seconds. 

Stocks are provided by [yfinance](https://github.com/ranaroussi/yfinance) and cached for 5 minutes.


**Environment Variables**

```
STREAMDECK_WEATHER_LOCATION="Europe/City"
STREAMDECK_WEATHER_LATITUDE="50.000"
STREAMDECK_WEATHER_LONGITUDE="10.000"
```

## TODO

Features and new plugins / scrollers I plan to add. I'm open to requests. 

### Existing Plugins

#### Tado 

- Analytics / stats info.

### New scrollers

- ? Suggestions welcome ?

## Installation

Run `setup.sh` with a working python 3 environment. It creates a venv for you and installs to that. 
Python 3.11 and bluetoothctl 5.66 or higher are required. 
Ubuntu Lunar works on Orange Pi Zero 2W
Raspbian based on Bookworm (12) on Raspberry Pi Zero 2W are known to work.

## Develop

Run the `develop.sh` script for setting up the venv and launching vs code.

## Run

Run :: `source ./venv/bin/activate && python ./streamdeck_launcher.py`

### Cron setup

To run under cron you need a bunch of settings in your crontab for VLC to be happy.

- Change
  - The token `YOU` for your actual username
  - 1000 to be your user number
  - The path to your clone of the repo
- Tested on Raspbian 12

```
SHELL=/usr/bin/bash
DISPLAY=:0
XDG_SESSION_TYPE=tty
HOME=/home/YOU
LANG=en_GB.UTF-8
XDG_SESSION_CLASS=user
TERM=xterm-256color
USER=YOU
SHLVL=1
XDG_SESSION_ID=4
XDG_RUNTIME_DIR=/run/user/1000
PULSE_RUNTIME_PATH=/run/user/1000/pulse
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/games:/usr/games
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus

@reboot /usr/bin/sleep 30 && cd /home/YOU/code/streamdeck-pi-home && /home/YOU/code/streamdeck-pi-home/run.sh
0 3 * * 1 sudo /usr/sbin/reboot

```

The `run.sh`` file is included here.

### LEDs

To turn off the software controllable Leds, add something like this to your `/ect/rc.local`.

```
echo none > /sys/class/leds/green_led/trigger
echo none > /sys/class/leds/100m_link/trigger
echo none > /sys/class/leds/100m_act/trigger
```

## Thanks to the following projects

This project is made using the following libraries :
- adb_shell
- homekit
- jellyfin-apiclient-python
- libsonic
- phue
- python-tado
- python-vlc
- streamdeck

and beautiful assets from : 
- piotezaza streamdeck icon pack
- Terminator Font by www.norfok.com
