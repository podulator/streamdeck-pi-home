"""
Shared test fixtures for streamdeck-pi-home.

Provides mock objects for all external dependencies:
- Stream Deck hardware (buttons, dials, touchscreen)
- VLC media player
- NFC reader
- PIL image operations
- Config structures

All fixtures return lightweight mocks that satisfy the interfaces
without touching real hardware or networks.

IMPORTANT — stub ordering:
Module stubs for hardware/third-party libs MUST be installed into
sys.modules before any project code is imported. This file is
processed by pytest before test collection, so it's the right place.
"""
import sys
import os
import re
import types
import pytest
from unittest.mock import MagicMock, PropertyMock
from pathlib import Path
from enum import Enum

# ---------------------------------------------------------------------------
# Helper: make a stub module with named attributes
# ---------------------------------------------------------------------------

def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# ---------------------------------------------------------------------------
# StreamDeck SDK stubs
# ---------------------------------------------------------------------------

class _DialEventType(Enum):
    PUSH = "push"
    TURN = "turn"

_stub("StreamDeck")
_stub("StreamDeck.Devices")
_stub(
    "StreamDeck.Devices.StreamDeck",
    DialEventType=_DialEventType,
    StreamDeck=MagicMock,
)
_stub(
    "StreamDeck.DeviceManager",
    DeviceManager=MagicMock,
    StreamDeckPlus=MagicMock,
)

# ---------------------------------------------------------------------------
# VLC stubs
# ---------------------------------------------------------------------------

class _VlcState(Enum):
    NothingSpecial = 0
    Opening = 1
    Buffering = 2
    Playing = 3
    Paused = 4
    Stopped = 5
    Ended = 6
    Error = 7

class _EventType(Enum):
    MediaPlayerOpening = "opening"
    MediaPlayerPaused = "paused"
    MediaPlayerStopped = "stopped"
    MediaPlayerEndReached = "end"
    MediaPlayerEncounteredError = "error"
    MediaPlayerPlaying = "playing"

_stub(
    "vlc",
    State=_VlcState,
    EventType=_EventType,
    MediaParseFlag=MagicMock,
    Meta=MagicMock,
    Instance=MagicMock,
    MediaPlayer=MagicMock,
    EventManager=MagicMock,
    Media=MagicMock,
)

# ---------------------------------------------------------------------------
# NFC stubs
# ---------------------------------------------------------------------------

_stub("nfc")
_stub("nfc.clf")
_stub("nfcpy")
_stub("ndef")
_stub("ndef.message")
_stub("ndef.record")
# nfc_reader module stub — prevents importing the real nfc_reader.py
# which requires hardware deps (ndef, nfc)
if "nfc_reader" not in sys.modules:
    _nfc_reader_mod = _stub("nfc_reader", NfcDevice=MagicMock)

# ---------------------------------------------------------------------------
# adb_shell stubs — FireTV plugin imports these at module level
# ---------------------------------------------------------------------------

_stub("adb_shell")
_stub("adb_shell.adb_device", AdbDeviceTcp=MagicMock, AdbDeviceUsb=MagicMock)
_stub("adb_shell.auth")
_stub("adb_shell.auth.sign_pythonrsa", PythonRSASigner=MagicMock)
_stub("adb_shell.auth.keygen", keygen=MagicMock)

# ---------------------------------------------------------------------------
# requests_cache / retry_requests — Stocks scroller imports at module level
# ---------------------------------------------------------------------------

_stub("requests_cache", CachedSession=MagicMock, SQLiteCache=MagicMock)
_stub("retry_requests", retry=MagicMock)

# ---------------------------------------------------------------------------
# Other third-party plugin/scroller deps
# ---------------------------------------------------------------------------

for _mod_name in [
    "phue",
    "pexpect",
    "tinytuya",
    "pyvesync",
    "pyvesync.vesyncfan",
    "homekit",
    "homekit.controller",
    "homekit.model",
    "homekit.model.characteristics",
    "homekit.model.services",
    "libsonic",
    "jellyfin_apiclient_python",
    "jellyfin_apiclient_python.api",
    "yfinance",
    "rgbxy",
    "python_tado",
    "requests",
    "requests.exceptions",
]:
    if _mod_name not in sys.modules:
        _stub(_mod_name)

# python_tado may also be imported as 'libtado'
_stub("libtado")
_stub("libtado.api")

# ---------------------------------------------------------------------------
# dotenv stub
# ---------------------------------------------------------------------------

if "dotenv" not in sys.modules:
    _stub("dotenv", load_dotenv=lambda *a, **kw: None)

# ---------------------------------------------------------------------------
# envsubst stub — actually performs ${VAR} substitution using os.environ
# This mirrors what the real envsubst library does.
# ---------------------------------------------------------------------------

def _real_envsubst(text: str) -> str:
    """Replace ${VAR} and $VAR tokens using os.environ."""
    def _replace(match):
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, match.group(0))
    # Handle ${VAR} and $VAR
    return re.sub(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)', _replace, text)

if "envsubst" not in sys.modules:
    _stub("envsubst", envsubst=_real_envsubst)
else:
    # Already registered by a previous import — patch it with a working version
    sys.modules["envsubst"].envsubst = _real_envsubst

# ---------------------------------------------------------------------------
# Add project root to sys.path
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def font_config():
    """Standard font config dict matching config.json structure."""
    return {
        "font_path": "font/terminator.otf",
        "font_size": 80,
        "background_color": "black",
    }


@pytest.fixture
def mock_deck():
    """
    A mock Stream Deck + device with realistic constants.

    Provides KEY_COUNT, TOUCHSCREEN_PIXEL_WIDTH/HEIGHT, and stubs for
    all hardware methods (set_key_image, set_touchscreen_image, etc).
    """
    deck = MagicMock()
    deck.KEY_COUNT = 8
    deck.TOUCHSCREEN_PIXEL_WIDTH = 800
    deck.TOUCHSCREEN_PIXEL_HEIGHT = 100
    deck.DECK_TYPE = "Stream Deck +"
    deck.deck_type.return_value = "Stream Deck +"
    deck.get_serial_number.return_value = "TEST123"
    return deck


@pytest.fixture
def mock_app(mock_deck, font_config):
    """
    A mock App instance that satisfies what IPlugin and IScroller expect.

    Has realistic screen dimensions, num_buttons, and stub methods for
    set_button_image, load_image, etc.
    """
    app = MagicMock()
    app.deck = mock_deck
    app.num_buttons = 8
    app.screen_width = 800
    app.screen_height = 100
    app.config = {
        "debug": 1,
        "creds_path": ".creds",
        "brightness": {"minimum": 10, "press_to_wake": 30, "initial": 100},
        "font": font_config,
    }
    app.creds_path = ".creds"
    app.is_debug_enabled = True
    app.load_image.return_value = b"\xff\xd8\xff\xe0"  # fake JPEG header
    app.set_button_image.return_value = None
    return app


@pytest.fixture
def plugin_config():
    """Minimal plugin config entry — enough to instantiate IPlugin."""
    return {
        "name": "Test Plugin",
        "class": "blank",
        "config": {},
    }


@pytest.fixture
def scroller_config():
    """Minimal scroller config entry."""
    return {
        "name": "Test Scroller",
        "class": "text",
        "config": {
            "lines": ["Hello", "World"],
        },
    }


@pytest.fixture
def full_config(font_config):
    """A complete config dict matching config.json top-level structure."""
    return {
        "debug": 1,
        "creds_path": ".creds",
        "idle_time_minutes": 15,
        "nfc_device": "tty:USB0",
        "brightness": {
            "minimum": 10,
            "press_to_wake": 30,
            "initial": 100,
        },
        "font": font_config,
        "plugins": [
            {"name": "Blank", "class": "blank", "config": {}},
        ],
        "scrollers": [
            {
                "name": "Greeting",
                "class": "text",
                "config": {"lines": ["Hello"]},
            },
        ],
    }


@pytest.fixture
def sample_artists():
    """Pre-built artist/album/track hierarchy for player tests."""
    # Import directly — bypasses the plugin package __init__
    sys.path.insert(0, str(_PROJECT_ROOT))
    from plugins.shared.player.types import Artist, Album, Track

    track1 = Track("t1", "first_song", "album_one", "artist_one", 1, "http://example.com/1.mp3")
    track2 = Track("t2", "second_song", "album_one", "artist_one", 2, "http://example.com/2.mp3")
    track3 = Track("t3", "third_song", "album_two", "artist_one", 1, "http://example.com/3.mp3")

    album1 = Album("a1", "album_one", "artist_one", 2020)
    album1.tracks = [track1, track2]

    album2 = Album("a2", "album_two", "artist_one", 2022)
    album2.tracks = [track3]

    artist = Artist("ar1", "artist_one")
    artist.albums = [album1, album2]

    return {
        "artists": [artist],
        "albums": [album1, album2],
        "tracks": [track1, track2, track3],
    }


# ---------------------------------------------------------------------------
# Scroller submodule stubs — IScroller.py does `from . import text` etc.
# which triggers scrollers/__init__.py importing all real scroller classes.
# Stub the leaf modules so imports don't pull in real deps.
# ---------------------------------------------------------------------------

# Scroller stubs: IScroller.py imports text_scroller.text.TextScroller
# so scrollers.text needs a .text sub-module with TextScroller on it.
_SCROLLER_MAP = {
    "clock": "ClockScroller",
    "cmd": "CmdScroller",
    "date": "DateScroller",
    "stocks": "StocksScroller",
    "text": "TextScroller",
    "weather": "WeatherScroller",
}
for _sname, _scls in _SCROLLER_MAP.items():
    _leaf_mod_name = f"scrollers.{_sname}.{_sname}"
    _parent_mod_name = f"scrollers.{_sname}"
    # Use a plain class stub (not MagicMock) so it can be instantiated
    # with MagicMock args without triggering InvalidSpecError.
    _stub_cls_name = _scls
    _stub_cls = type(_stub_cls_name, (), {"__init__": lambda self, *a, **kw: None})
    # leaf: scrollers.text.text
    if _leaf_mod_name not in sys.modules:
        _leaf = types.ModuleType(_leaf_mod_name)
        sys.modules[_leaf_mod_name] = _leaf
    _leaf = sys.modules[_leaf_mod_name]
    setattr(_leaf, _scls, _stub_cls)
    # parent: scrollers.text — must have .text pointing at the leaf
    if _parent_mod_name not in sys.modules:
        _parent = types.ModuleType(_parent_mod_name)
        sys.modules[_parent_mod_name] = _parent
    _parent = sys.modules[_parent_mod_name]
    setattr(_parent, _sname, sys.modules[_leaf_mod_name])
    setattr(_parent, _scls, _stub_cls)

# Stub the plugin leaf modules AND the plugins package __init__ so that
#  and  both work
# without importing real hardware-dependent plugin classes.
_PLUGIN_CLASS_MAP = {
    "plugins.blank.blank": "BlankPlugin",
    "plugins.bluetooth.bluetooth": "BluetoothPlugin",
    "plugins.firetv.firetv": "FireTvPlugin",
    "plugins.hue.hue": "HuePlugin",
    "plugins.jellyfin.jellyfin": "JellyfinPlugin",
    "plugins.levoit.levoit": "LevoitPlugin",
    "plugins.radio.radio": "RadioPlugin",
    "plugins.settings.settings": "SettingsPlugin",
    "plugins.subsonic.subsonic": "SubsonicPlugin",
    "plugins.tado.tado": "TadoPlugin",
    "plugins.tuya.tuya": "VacuumPlugin",
    "plugins.velux.velux": "VeluxPlugin",
}
for _pmod, _pcls in _PLUGIN_CLASS_MAP.items():
    # parent package stub e.g. plugins.blank
    _ppkg = ".".join(_pmod.split(".")[:-1])
    if _ppkg not in sys.modules:
        sys.modules[_ppkg] = types.ModuleType(_ppkg)
    # leaf module stub e.g. plugins.blank.blank
    if _pmod not in sys.modules:
        _m = types.ModuleType(_pmod)
        sys.modules[_pmod] = _m
    _m = sys.modules[_pmod]
    if not hasattr(_m, _pcls):
        setattr(_m, _pcls, MagicMock)
    # Also expose the class on the parent package (plugins.blank.BlankPlugin)
    setattr(sys.modules[_ppkg], _pcls, MagicMock)

# Stub the plugins package itself to prevent __init__.py from running real imports
if "plugins" not in sys.modules:
    _plugins_pkg = types.ModuleType("plugins")
    _plugins_pkg.__path__ = [str(_PROJECT_ROOT / "plugins")]
    _plugins_pkg.__package__ = "plugins"
    sys.modules["plugins"] = _plugins_pkg
# Ensure all plugin classes are on the plugins package
for _pcls in ["BlankPlugin","BluetoothPlugin","FireTvPlugin","HuePlugin",
              "JellyfinPlugin","LevoitPlugin","RadioPlugin","SettingsPlugin",
              "SubsonicPlugin","TadoPlugin","VacuumPlugin","VeluxPlugin"]:
    if not hasattr(sys.modules["plugins"], _pcls):
        setattr(sys.modules["plugins"], _pcls, MagicMock)
