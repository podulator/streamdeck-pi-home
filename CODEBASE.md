# CODEBASE.md — Architecture & Developer Guide

> Developer-facing reference for the `streamdeck-pi-home` codebase.
> For user-facing docs (plugin controls, environment variables, installation), see [README.md](README.md).

## Project Overview

A Python application that drives an Elgato Stream Deck + as a physical smart-home controller. It uses a plugin/scroller architecture: **plugins** own the buttons and dials when activated, while **scrollers** cycle informational content on the touchscreen during idle. An NFC reader provides tag-driven shortcuts. Audio playback is handled via VLC through a shared player abstraction.

## Directory Structure

```
.
├── streamdeck_launcher.py   # Entry point — device detection, config loading, signal handling
├── app.py                   # Core App class — lifecycle, callbacks, main loop, layout management
├── nfc_reader.py            # NFC tag reader (PN532) via nfcpy — blocking listen in a daemon thread
├── config.json              # Primary configuration — plugins, scrollers, font, brightness, NFC device
├── requirements.txt         # Python dependencies (pinned lower bounds)
├── setup.sh                 # First-run setup — udev rules, venv creation, pip install
├── run.sh                   # Production launcher — activates venv, runs with auto-restart on SIGABRT (134)
├── update.sh                # Git pull with local modification guard + silent pip upgrade
├── develop.sh               # Activates venv + launches VS Code
├── font/                    # Custom fonts for touchscreen rendering (Terminator OTF/TTF, Birdfont source)
├── images/                  # Shared images (home button, next page, etc.)
├── .creds/                  # [gitignored] Runtime credentials (Hue bridge, ADB keys, Velux pairing)
├── plugins/                 # Plugin system — each subdirectory is a plugin
│   ├── __init__.py
│   ├── IPlugin.py           # ABC base class + PluginFactory + text rendering engine
│   ├── images/              # Shared plugin images (back button)
│   ├── shared/              # Shared utilities across plugins
│   │   └── player/          # VLC-based audio player abstraction (used by subsonic, jellyfin, radio)
│   │       ├── iplayer.py   # IPlayer — abstract media browser with Artist→Album→Track navigation
│   │       ├── vlc_player.py# VlcPlayer — python-vlc wrapper with playlist, events, callbacks
│   │       └── types.py     # Data models: Artist, Album, Track, Playlist
│   ├── blank/               # NOOP plugin (placeholder button)
│   ├── bluetooth/           # Bluetooth device scanning + connection via bluetoothctl/pexpect
│   ├── firetv/              # Fire TV control via ADB shell
│   ├── hue/                 # Philips Hue lights via phue
│   ├── jellyfin/            # Jellyfin music client (extends IPlayer)
│   ├── levoit/              # Levoit air purifier via pyvesync
│   ├── radio/               # Internet radio streamer (uses VlcPlayer directly)
│   ├── settings/            # System controls (reboot, update, reload, save settings)
│   ├── subsonic/            # Subsonic/Navidrome music client (extends IPlayer)
│   ├── tado/                # Tado heating via python-tado
│   ├── tuya/                # Tuya vacuum via tinytuya
│   └── velux/               # Velux KIX300 accessories via homekit
└── scrollers/               # Scroller system — each subdirectory is a scroller type
    ├── __init__.py
    ├── IScroller.py         # ABC base class + ScrollerFactory + background rendering
    ├── clock/               # Current time display
    ├── cmd/                 # Shell command output display
    ├── date/                # Date display
    ├── stocks/              # Stock ticker via yfinance
    ├── text/                # Static text display
    └── weather/             # Weather via Open-Meteo API (cached)
```

## Core Architecture

### Startup Flow

1. **`streamdeck_launcher.py`** — Entry point (`__main__`):
   - Loads `.env` via `python-dotenv`
   - Reads `config.json`, applies `envsubst` for `${VAR}` expansion in config values
   - Polls `DeviceManager().enumerate()` looking for a `Stream Deck +` device
   - Instantiates `App(deck, config)` and calls `app.run()`
   - Handles `SIGINT` for clean shutdown
   - Outer loop reconnects if the deck errors out (with 5s backoff)

2. **`app.py` → `App.run()`**:
   - Opens the deck, registers hardware callbacks (`set_key_callback`, `set_dial_callback`)
   - Loads plugins via `PluginFactory.create_plugin()` from config
   - Loads scrollers via `ScrollerFactory.create_scroller()` from config
   - Starts NFC reader on a daemon thread
   - Sets the default button layout (home + plugin logos, paginated if > 7 plugins)
   - Starts `_main_loop` on a non-daemon thread

### Main Loop (`App._main_loop`)

Runs on a 1-second tick with a 15-second scroller rotation cycle:

- **Every 15 seconds**: advances the active scroller (cycles pages, then moves to next scroller)
- **Every ~5 minutes**: dims the screen by 10% (down to configured minimum)
- **Idle timeout**: if the active plugin reports `idle == True` for `idle_time_minutes`, deactivates it and returns home
- **NFC watchdog**: restarts the NFC listener if it stopped

### Event Handling

All hardware events flow through two callbacks on `App`:

- **`_key_change_callback(deck, key, key_state)`** — Button presses:
  - Wakes screen if dim (below `press_to_wake` threshold — consumes the press)
  - In home mode: key 0 = reset home, last key = next page, others = activate plugin
  - In plugin mode: key 0 = back (long-press = help), others forwarded to plugin
  - Key-up in home mode triggers `_default_layout()` refresh

- **`_dial_change_callback(deck, dial, event, value)`** — Dial turns and pushes:
  - Maintains a `_button_mask` bitmask; pressing dials 3+4 simultaneously triggers `destroy()` (emergency shutdown)
  - In home mode: dial 3 = scroll through scrollers, dial 4 = brightness control
  - In plugin mode: forwarded to the active plugin

### NFC Integration

`NfcDevice` (in `nfc_reader.py`) uses `nfcpy` with a blocking `connect(rdwr=...)` call on a daemon thread. Tags must be NDEF-formatted with text records. Tag payload format: `<plugin_class>::<action>`. The app routes the tag to the matching plugin's `action_from_string()` method, activating it first if needed.

## Plugin System

### Interface: `IPlugin` (ABC)

All plugins extend `IPlugin` from `plugins/IPlugin.py`. Key lifecycle methods:

| Method | Purpose |
|--------|---------|
| `__init__(app, config, font)` | Receives app reference, per-plugin config dict, font settings |
| `activate() → bool` | Called when user enters the plugin. Sets up layout, shows loading screen. Returns `False` to abort |
| `deactivate()` | Called when user leaves. Plugin keeps state for re-entry |
| `destroy()` | Final cleanup (app shutdown) |
| `run_as_daemon()` | Called once at startup — for background threads (e.g., bluetooth monitoring) |
| `on_button_press(deck, key, key_state)` | Handle button events (key 0 / back is handled by App) |
| `on_dial_turned(deck, dial, value)` | Handle dial rotation |
| `on_dial_pushed(deck, dial, state)` | Handle dial press |
| `action_from_string(action)` | Handle NFC tag payload |
| `handle_back_button() → bool` | Return `True` to handle back internally (nested navigation), `False` to deactivate |
| `show_help()` / `hide_help()` | Long-press back button shows a help overlay |

### Built-in Services

`IPlugin` provides to subclasses:

- **`_render(text, font_size, font_path, bg_color)`** — Renders text to the touchscreen with auto-wrapping, centring, and font-size scaling. Thread-safe via `_RenderLock`. Caches last render for help overlay restore.
- **`_load_images(collection, keys)`** — Bulk-loads images from the plugin's `images/` directory.
- **`_wrap(index, length)`** — Modular wrap for rotary selection.
- **`logo`** / **`back_button`** — Auto-loaded from `<plugin>/images/logo.png` and `plugins/images/back.png`.

### Plugin Registration

`PluginFactory.create_plugin()` uses a `match/case` on `config["class"]` to instantiate the correct class. **Plugins are not dynamically discovered** — adding a new plugin requires:

1. Creating a `plugins/<name>/` directory with `__init__.py`, `<name>.py`, and `images/logo.png`
2. The plugin class extends `IPlugin`
3. Adding an `import` in `plugins/IPlugin.py`
4. Adding a `case` branch in `PluginFactory.create_plugin()`
5. Adding a config entry in `config.json`

### Plugin Directory Convention

Each plugin lives in `plugins/<class_name>/`:
```
plugins/<name>/
├── __init__.py          # Usually empty
├── <name>.py            # Plugin class (e.g., HuePlugin, TadoPlugin)
├── images/
│   ├── logo.png         # Required — shown on home screen button
│   └── *.png            # Plugin-specific button/state images
├── shared.py            # Optional — shared constants/helpers
├── helper.py            # Optional — utility classes
├── controller.py        # Optional — hardware abstraction (e.g., bluetooth)
└── device.py            # Optional — device model classes
```

### Shared Player (`plugins/shared/player/`)

Music-playing plugins (Subsonic, Jellyfin, Radio) share a player stack:

- **`types.py`** — Data classes: `Artist`, `Album`, `Track`, `Playlist` with display name formatting (`string.capwords`) and JSON serialisation.
- **`VlcPlayer`** — Wraps `python-vlc`. Manages a playlist (`list[Track]`), loop mode, volume, mute. Emits events via callback: `PLAYING_MEDIA`, `PAUSED_MEDIA`, `MEDIA_ENDED`, `ERROR_OCCURRED`, `INFO_MESSAGE`, etc. Runs a "now playing" display thread that rotates between track name and full metadata every ~25 seconds.
- **`IPlayer(IPlugin)`** — Abstract media browser. Implements a hierarchical navigation state machine: `PARTITIONS → ARTISTS → ALBUMS → TRACKS`. Dial 1 navigates, dial 2 toggles info options, dial 3 manages playlist, dial 4 controls volume. Subclasses (Subsonic, Jellyfin) implement data fetching methods like `_get_stream_for_track()`, `_get_tracks_by_album()`, `_get_albums_by_artist()`.

## Scroller System

### Interface: `IScroller` (ABC)

Scrollers extend `IScroller` from `scrollers/IScroller.py`:

| Method | Purpose |
|--------|---------|
| `generate() → bytes` | Produce page content. Resets page counter, populates `_pages` list, returns first page |
| `deactivate()` | Cleanup |
| `next() → bytes` | Returns the next page as JPEG bytes, advances counter |
| `has_next → bool` | Whether more pages remain in current cycle |

The base class handles:
- Background image creation with a logo icon on the left
- Text rendering with auto-scaling font size
- Page iteration

### Scroller Registration

Same pattern as plugins — `ScrollerFactory.create_scroller()` with `match/case`. Falls back to a `TextScroller` with an error message for unknown classes.

## Configuration System

### `config.json`

The config file supports **environment variable substitution** via the `envsubst` library. Any `${VAR_NAME}` in the JSON is replaced with the corresponding env var at load time. Env vars are loaded from `.env` via `python-dotenv`.

Top-level keys:

| Key | Type | Description |
|-----|------|-------------|
| `debug` | `int` | Enables debug mode (deck can be `None`) |
| `creds_path` | `str` | Directory for credential files (default: `.creds`) |
| `idle_time_minutes` | `int` | Minutes before idle plugin auto-deactivates (default: 15) |
| `nfc_device` | `str` | NFC device path (e.g., `tty:USB0`) |
| `brightness` | `dict` | `minimum`, `press_to_wake`, `initial` brightness levels |
| `font` | `dict` | `font_path`, `font_size`, `background_color` — global text defaults |
| `plugins` | `list` | Array of plugin configs: `{name, class, config: {...}}` |
| `scrollers` | `list` | Array of scroller configs: `{name, class, config: {...}}` |

Each plugin/scroller entry has:
- `name` — display name (shown on loading screen)
- `class` — lookup key for the factory (`match/case`)
- `config` — plugin-specific settings (passed as `self._config`)

### Credentials

Stored in `.creds/` (gitignored). Plugins that need persistent credentials (Hue bridge pairing, ADB keys, Velux homekit pairing file) read/write from this directory via `app.creds_path`.

## Entry Points

| Command | Purpose |
|---------|---------|
| `python streamdeck_launcher.py [config.json]` | Run directly (optional config path argument) |
| `./run.sh` | Production launcher — venv activation + auto-restart on SIGABRT |
| `./setup.sh` | First-time setup — udev rules, venv, pip install |
| `./update.sh` | Safe git pull + pip upgrade (aborts on local modifications) |
| `./develop.sh` | Dev setup — activate venv + open VS Code |

### `run.sh` Restart Behaviour

The launcher wraps the Python process in a `while` loop. If the process exits with code 134 (SIGABRT), it restarts automatically after 5 seconds. Any other exit code breaks the loop. This handles VLC crashes and similar transient failures.

## Notable Patterns

### Threading Model
- **Main loop**: non-daemon thread with 1s sleep tick, manages scroller cycling and dimming
- **NFC reader**: daemon thread, blocking `nfc.connect()` call
- **Plugin daemon threads**: `run_as_daemon()` called at startup (e.g., bluetooth scanning)
- **VLC now-playing thread**: daemon thread in VlcPlayer, updates display every ~25s
- **Player run thread**: per-plugin thread that watches `_play_next` flag for playlist advancement
- **Render locks**: `IPlugin._RenderLock` (class-level) and `App._render_lock` prevent concurrent touchscreen writes

### Button Pagination
When there are more plugins than physical buttons (8), the home screen paginates. Button 0 is always Home, the last button becomes "Next Page". The `_page_counter` and `_num_pages` track navigation. Each page shows `num_buttons - 2` plugins (accounting for Home + Next).

### Image Handling
All button images are 120×120 JPEG. `App.load_image()` creates a black background, pastes the resized icon centred, and returns JPEG bytes. Touchscreen images are full-width JPEG rendered via PIL.

### Emergency Shutdown
Pressing dials 3 and 4 simultaneously triggers `App.destroy()` — the `_button_mask` bitmask tracks dial push state and checks for the `0b1100` pattern.

### Environment Variable Flow
`.env` → `load_dotenv()` → `os.environ` → `envsubst()` on `config.json` string → parsed JSON config. This means secrets stay in `.env` (gitignored) while the config structure stays in version control.

## Dependencies Overview

| Package | Used By | Purpose |
|---------|---------|---------|
| `streamdeck` | Core | Stream Deck + hardware interface (HID) |
| `Pillow` | Core | Image generation for buttons and touchscreen |
| `python-dotenv` | Core | `.env` file loading |
| `envsubst` | Core | `${VAR}` substitution in config |
| `python-vlc` | Player | VLC media playback |
| `nfcpy` | NFC | PN532 NFC tag reading |
| `adb-shell` | Fire TV | ADB protocol for Fire TV control |
| `phue` | Hue | Philips Hue bridge API |
| `python-tado` | Tado | Tado heating API |
| `homekit` | Velux | HomeKit accessory protocol |
| `jellyfin-apiclient-python` | Jellyfin | Jellyfin server API |
| `py-sonic` (libsonic) | Subsonic | Subsonic/Navidrome API |
| `pyvesync` | Levoit | VeSync cloud API for Levoit devices |
| `tinytuya` | Tuya | Local Tuya device control |
| `pexpect` | Bluetooth | `bluetoothctl` CLI automation |
| `rgbxy` | Hue | RGB ↔ CIE xy colour conversion |
| `yfinance` | Stocks scroller | Yahoo Finance stock data |
| `requests` / `requests-cache` / `retry-requests` | Weather, general | HTTP with caching and retry |
