"""
Tests for App — the core application class.

Covers:
- Emergency shutdown: dial 2+3 bitmask (0b1100) triggers destroy()
- Bitmask XOR logic: individual dial presses accumulate/clear correctly
- Key callback: wake-from-dim consumes press without forwarding to plugin
- Key callback: back button deactivates active plugin
- Key callback: nested back button (handle_back_button=True) keeps plugin active
- NFC callback: routes tag payload to matching plugin
- _deactivate_plugin: clears active plugin and resets counters
- _scroll: advances scroller pages, wraps to next scroller when exhausted,
           skips rendering when a plugin is active

Hardware deck and all plugins are fully mocked throughout.
App is imported directly — we do NOT call run() in any test.
"""
import sys
import types as _types_mod
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _load_app():
    """
    Import the App class, pre-stubbing the full plugin/scroller/NFC
    import chain so no hardware deps are touched.
    """
    import importlib.util

    # Ensure plugins and scrollers package stubs don't re-trigger imports
    # Note: conftest may have already set up plugins with __path__; only add
    # missing entries rather than overwriting existing ones.
    for pkg in [
        "plugins", "plugins.IPlugin",
        "scrollers", "scrollers.IScroller",
        "nfc_reader",
    ]:
        if pkg not in sys.modules:
            mod = _types_mod.ModuleType(pkg)
            if pkg == "plugins":
                import pathlib as _pl
                mod.__path__ = [str(_pl.Path(__file__).resolve().parent.parent / "plugins")]
                mod.__package__ = "plugins"
            sys.modules[pkg] = mod

    # Provide NfcDevice stub in the nfc_reader module
    nfc_reader_mod = sys.modules["nfc_reader"]
    if not hasattr(nfc_reader_mod, "NfcDevice"):
        nfc_reader_mod.NfcDevice = MagicMock

    # Provide IPlugin / PluginFactory / IScroller / ScrollerFactory stubs.
    # Use simple sentinel classes — NOT MagicMock — so other test files can
    # still import the real IPlugin without hitting InvalidSpecError.
    iplugin_mod = sys.modules["plugins.IPlugin"]
    if not hasattr(iplugin_mod, "IPlugin"):
        class _IPluginStub: pass
        class _PluginFactoryStub: pass
        iplugin_mod.IPlugin = _IPluginStub
        iplugin_mod.PluginFactory = _PluginFactoryStub

    iscroller_mod = sys.modules["scrollers.IScroller"]
    if not hasattr(iscroller_mod, "IScroller"):
        class _IScrollerStub: pass
        class _ScrollerFactoryStub:
            @staticmethod
            def create_scroller(*a, **kw): return MagicMock()
        iscroller_mod.IScroller = _IScrollerStub
        iscroller_mod.ScrollerFactory = _ScrollerFactoryStub

    # Also make PIL available (used by App.load_image)
    try:
        from PIL import Image
    except ImportError:
        pass  # PIL installed in test venv

    spec = importlib.util.spec_from_file_location("app", _ROOT / "app.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["app"] = mod
    spec.loader.exec_module(mod)
    return mod.App


# Load App once at module level
App = _load_app()

# Grab the DialEventType we set up in conftest
from StreamDeck.Devices.StreamDeck import DialEventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app_instance(full_config, mock_deck):
    """
    Construct an App with a mock deck and minimal wiring.
    run() is NOT called — we test methods directly.
    """
    app = App(mock_deck, full_config)
    mock_nfc = MagicMock()
    mock_nfc.is_listening = True
    app._nfc = mock_nfc
    app._plugins = []
    app._scrollers = []
    app._home_image = b"\xff\xd8"
    app._next_page_image = b"\xff\xd8"
    return app


@pytest.fixture
def app_with_plugins(app_instance):
    """App instance with two pre-built mock plugins."""
    plugin_a = MagicMock()
    plugin_a.name = "Plugin A"
    plugin_a.plugin_class = "blank"
    plugin_a.idle = True
    plugin_a.logo = b"\xff\xd8"
    plugin_a.activate.return_value = True
    plugin_a.help_showing = False
    plugin_a.handle_back_button.return_value = False

    plugin_b = MagicMock()
    plugin_b.name = "Plugin B"
    plugin_b.plugin_class = "radio"
    plugin_b.idle = False
    plugin_b.logo = b"\xff\xd8"
    plugin_b.activate.return_value = True
    plugin_b.help_showing = False
    plugin_b.handle_back_button.return_value = False

    app_instance._plugins = [plugin_a, plugin_b]
    app_instance._num_pages = 1
    app_instance._page_counter = 0
    return app_instance, plugin_a, plugin_b


@pytest.fixture
def app_with_scrollers(app_instance):
    """App instance with two pre-built mock scrollers."""
    scroller_a = MagicMock()
    scroller_a.name = "Scroller A"
    scroller_a.has_next = True
    scroller_a.next.return_value = b"\xff\xd8\xff"

    scroller_b = MagicMock()
    scroller_b.name = "Scroller B"
    scroller_b.has_next = False
    scroller_b.generate.return_value = b"\xff\xd8\xff"

    app_instance._scrollers = [scroller_a, scroller_b]
    app_instance._active_scroller = 0
    return app_instance, scroller_a, scroller_b


# ---------------------------------------------------------------------------
# Emergency shutdown
# ---------------------------------------------------------------------------

class TestEmergencyShutdown:
    """Dial 2 + 3 pressed simultaneously (bits 2+3 = 0b1100) calls destroy()."""

    def test_single_dial_push_does_not_shutdown(self, app_instance):
        """Pressing only dial 2 sets one bit but does NOT trigger destroy."""
        with patch.object(app_instance, "destroy") as mock_destroy:
            app_instance._button_mask = 0
            app_instance._dial_change_callback(mock_deck := app_instance._deck, 2, DialEventType.PUSH, True)
            mock_destroy.assert_not_called()

    def test_dials_2_and_3_triggers_destroy(self, app_instance):
        """Pressing dials at index 2 and 3 sets mask to 0b1100 and triggers destroy."""
        with patch.object(app_instance, "destroy") as mock_destroy:
            app_instance._button_mask = 0
            app_instance._dial_change_callback(app_instance._deck, 2, DialEventType.PUSH, True)
            mock_destroy.assert_not_called()
            app_instance._dial_change_callback(app_instance._deck, 3, DialEventType.PUSH, True)
            mock_destroy.assert_called_once()

    def test_bitmask_xor_accumulates_on_press(self, app_instance):
        """Each PUSH event XORs the dial's bit into the bitmask."""
        with patch.object(app_instance, "destroy"):
            app_instance._button_mask = 0
            app_instance._dial_change_callback(app_instance._deck, 0, DialEventType.PUSH, True)
            assert app_instance._button_mask & (1 << 0)

    def test_bitmask_xor_clears_on_second_press(self, app_instance):
        """XOR-ing the same bit twice clears it (toggle behaviour)."""
        with patch.object(app_instance, "destroy"):
            app_instance._button_mask = 0
            # Press
            app_instance._dial_change_callback(app_instance._deck, 0, DialEventType.PUSH, True)
            assert app_instance._button_mask & (1 << 0)
            # Press again (or release — same event fires with False)
            app_instance._dial_change_callback(app_instance._deck, 0, DialEventType.PUSH, False)
            assert not (app_instance._button_mask & (1 << 0))

    def test_destroy_sets_destroyed_flag(self, app_instance):
        """destroy() should set _destroyed = True."""
        app_instance._plugins = []
        app_instance._scrollers = []
        app_instance.destroy()
        assert app_instance._destroyed is True


# ---------------------------------------------------------------------------
# Plugin management via key callbacks
# ---------------------------------------------------------------------------

class TestPluginManagement:
    """Plugin activation and deactivation via key events."""

    def test_activate_plugin_via_key_press(self, app_with_plugins):
        """Pressing key 1 in home mode should activate the first plugin."""
        app, plugin_a, plugin_b = app_with_plugins
        app._active_plugin = None
        app._brightness = 100

        app._key_change_callback(app._deck, 1, True)

        plugin_a.activate.assert_called_once()
        assert app._active_plugin == plugin_a

    def test_failed_activate_deactivates_immediately(self, app_with_plugins):
        """If activate() returns False, _active_plugin should be cleared."""
        app, plugin_a, _ = app_with_plugins
        plugin_a.activate.return_value = False
        app._active_plugin = None
        app._brightness = 100

        app._key_change_callback(app._deck, 1, True)

        assert app._active_plugin is None

    def test_back_button_key_up_deactivates_plugin(self, app_with_plugins):
        """Key 0 key-up in plugin mode should deactivate the plugin."""
        app, plugin_a, _ = app_with_plugins
        app._active_plugin = plugin_a
        app._brightness = 100

        app._key_change_callback(app._deck, 0, False)

        plugin_a.deactivate.assert_called_once()
        assert app._active_plugin is None

    def test_back_button_nested_keeps_plugin_active(self, app_with_plugins):
        """If handle_back_button() returns True, the plugin stays active."""
        app, plugin_a, _ = app_with_plugins
        app._active_plugin = plugin_a
        plugin_a.handle_back_button.return_value = True
        app._brightness = 100

        app._key_change_callback(app._deck, 0, False)

        plugin_a.deactivate.assert_not_called()
        assert app._active_plugin == plugin_a

    def test_dim_press_wakes_without_activating_plugin(self, app_with_plugins):
        """A key press when screen is dim should wake it but not activate a plugin."""
        app, plugin_a, _ = app_with_plugins
        app._active_plugin = None
        # Below press_to_wake threshold (30)
        app._brightness = 10

        app._key_change_callback(app._deck, 1, True)

        plugin_a.activate.assert_not_called()
        assert app._active_plugin is None
        # Wake side-effect: brightness should be restored to 100
        assert app._brightness == 100


# ---------------------------------------------------------------------------
# Scroller cycling
# ---------------------------------------------------------------------------

class TestScrollerCycling:
    """_scroll advances pages and wraps between scrollers."""

    def test_scroll_calls_next_when_has_next(self, app_with_scrollers):
        """_scroll should call next() on the active scroller if it has pages."""
        app, scroller_a, _ = app_with_scrollers
        app._active_plugin = None

        with patch.object(app, "_render_scroller_image") as mock_render:
            app._scroll()

        scroller_a.next.assert_called_once()
        mock_render.assert_called_once()

    def test_scroll_advances_to_next_scroller_when_exhausted(self, app_with_scrollers):
        """When active scroller is exhausted, _scroll should move to the next one."""
        app, scroller_a, scroller_b = app_with_scrollers
        scroller_a.has_next = False
        app._active_plugin = None
        app._active_scroller = 0

        with patch.object(app, "_render_scroller_image"):
            app._scroll()

        assert app._active_scroller == 1
        scroller_b.generate.assert_called_once()

    def test_scroll_wraps_around_to_first_scroller(self, app_with_scrollers):
        """After the last scroller exhausts, active_scroller should wrap to 0."""
        app, scroller_a, scroller_b = app_with_scrollers
        scroller_b.has_next = False
        app._active_plugin = None
        app._active_scroller = 1  # currently on last scroller

        with patch.object(app, "_render_scroller_image"):
            app._scroll()

        assert app._active_scroller == 0

    def test_scroll_noop_when_plugin_active(self, app_with_scrollers):
        """_scroll should not update the screen when a plugin is active."""
        app, scroller_a, _ = app_with_scrollers
        app._active_plugin = MagicMock()

        with patch.object(app, "_render_scroller_image") as mock_render:
            app._scroll()

        mock_render.assert_not_called()


# ---------------------------------------------------------------------------
# NFC routing
# ---------------------------------------------------------------------------

class TestNfcRouting:
    """NFC tag payloads are routed to the correct plugin."""

    def test_nfc_activates_matching_plugin(self, app_with_plugins):
        """A tag matching a plugin class should activate that plugin and call action_from_string."""
        app, plugin_a, plugin_b = app_with_plugins
        plugin_a.plugin_class = "blank"
        plugin_a.activate.return_value = True
        app._active_plugin = None

        app._nfc_read_callback("blank::some_action")

        plugin_a.activate.assert_called_once()
        plugin_a.action_from_string.assert_called_with("some_action")

    def test_nfc_no_matching_class_does_nothing(self, app_with_plugins):
        """A tag with no matching plugin class should not activate anything."""
        app, plugin_a, plugin_b = app_with_plugins
        app._active_plugin = None

        app._nfc_read_callback("unknown_class::action")

        plugin_a.activate.assert_not_called()
        plugin_b.activate.assert_not_called()

    def test_nfc_empty_payload_is_ignored(self, app_with_plugins):
        """An empty or whitespace-only NFC payload should be silently ignored."""
        app, plugin_a, plugin_b = app_with_plugins

        app._nfc_read_callback("   ")  # should not raise

        plugin_a.activate.assert_not_called()

    def test_nfc_malformed_no_separator_does_not_crash(self, app_with_plugins):
        """A tag without '::' separator should not raise (logged as error only)."""
        app, plugin_a, plugin_b = app_with_plugins

        app._nfc_read_callback("malformed_tag_no_separator")  # no crash

        plugin_a.activate.assert_not_called()

    def test_nfc_destroyed_app_ignores_callback(self, app_with_plugins):
        """If the app is destroyed, NFC callback should return early."""
        app, plugin_a, _ = app_with_plugins
        app._destroyed = True

        app._nfc_read_callback("blank::action")

        plugin_a.activate.assert_not_called()

    def test_nfc_activate_failure_clears_plugin(self, app_with_plugins):
        """If plugin.activate() returns False via NFC, active plugin should be cleared."""
        app, plugin_a, _ = app_with_plugins
        plugin_a.plugin_class = "blank"
        plugin_a.activate.return_value = False
        app._active_plugin = None

        app._nfc_read_callback("blank::some_action")

        plugin_a.activate.assert_called_once()
        plugin_a.deactivate.assert_called_once()
        # action_from_string should NOT be called since activate failed
        plugin_a.action_from_string.assert_not_called()
        assert app._active_plugin is not plugin_a
