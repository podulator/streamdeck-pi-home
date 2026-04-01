"""
Tests for the IPlugin interface contract.

These tests verify the behaviour that ALL plugins must satisfy:
- Lifecycle (init → activate → deactivate → destroy)
- Button/dial event forwarding
- Help overlay show/hide
- Render caching
- Property contracts (name, plugin_class, idle, back_button)

We test via a concrete minimal subclass to avoid importing the full
plugin package (which pulls in hardware deps). Instead we import
IPlugin directly from its module file.
"""
import sys
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


def _make_minimal_plugin(mock_app, font_config, name="Test", cls="blank", config=None):
    """
    Construct a minimal concrete IPlugin subclass.
    conftest.py stubs all hardware/plugin deps before collection.
    We ensure the plugins package stub has __path__ set so that relative
    imports in IPlugin.py resolve to our stubs, then do a plain import.
    """
    import sys as _sys
    import types as _types
    root = Path(__file__).resolve().parent.parent

    # Ensure plugins package stub has __path__ so relative imports work
    if "plugins" not in _sys.modules:
        _pkg = _types.ModuleType("plugins")
        _pkg.__path__ = [str(root / "plugins")]
        _pkg.__package__ = "plugins"
        _sys.modules["plugins"] = _pkg
    else:
        _pkg = _sys.modules["plugins"]
        if not hasattr(_pkg, "__path__") or not _pkg.__path__:
            _pkg.__path__ = [str(root / "plugins")]
            _pkg.__package__ = "plugins"

    # Force re-import of the real IPlugin module (in case stub is cached)
    _sys.modules.pop("plugins.IPlugin", None)

    from plugins.IPlugin import IPlugin

    class MinimalPlugin(IPlugin):
        pass

    cfg = {"name": name, "class": cls, "config": config or {}}
    return MinimalPlugin(mock_app, cfg, font_config)


class TestIPluginLifecycle:
    """Verify the plugin lifecycle transitions."""

    def test_init_sets_name_and_class(self, mock_app, font_config):
        """IPlugin.__init__ should store name and class from config."""
        plugin = _make_minimal_plugin(mock_app, font_config, name="My Plugin", cls="blank")
        assert plugin.name == "My Plugin"
        assert plugin.plugin_class == "blank"

    def test_init_stores_plugin_config(self, mock_app, font_config):
        """The inner 'config' dict should be accessible via .config property."""
        plugin = _make_minimal_plugin(mock_app, font_config, config={"secret": 42})
        assert plugin._config == {"secret": 42}
        assert plugin.config == {"secret": 42}

    def test_not_activated_after_init(self, mock_app, font_config):
        """A freshly constructed plugin should not be activated."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        assert plugin._activated is False

    def test_activate_sets_activated_flag(self, mock_app, font_config):
        """activate() should set _activated = True and render a loading screen."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        with patch.object(plugin, "_render", return_value=True):
            result = plugin.activate()
        assert result is True
        assert plugin._activated is True
        # Should set button 0 to back button
        mock_app.set_button_image.assert_any_call(0, plugin.back_button)

    def test_deactivate_clears_activated(self, mock_app, font_config):
        """deactivate() should set _activated = False."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        with patch.object(plugin, "_render", return_value=True):
            plugin.activate()
        plugin.deactivate()
        assert plugin._activated is False

    def test_idle_defaults_to_true(self, mock_app, font_config):
        """Default idle property should return True — plugins override if they have work."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        assert plugin.idle is True

    def test_handle_back_button_defaults_false(self, mock_app, font_config):
        """Default handle_back_button returns False — meaning 'deactivate me'."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        assert plugin.handle_back_button() is False


class TestIPluginHelp:
    """Verify the help overlay mechanism."""

    def test_show_help_sets_flag(self, mock_app, font_config):
        """show_help() should render help text and set help_showing flag."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        plugin._activated = True
        with patch.object(plugin, "_render", return_value=True):
            plugin.show_help()
        assert plugin.help_showing is True

    def test_hide_help_clears_flag(self, mock_app, font_config):
        """hide_help() should clear help_showing."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        plugin._activated = True
        with patch.object(plugin, "_render", return_value=True):
            plugin.show_help()
            plugin.hide_help()
        assert plugin.help_showing is False

    def test_show_help_preserves_cache(self, mock_app, font_config):
        """show_help() should save the previous render cache so hide_help() can restore it."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        plugin._activated = True

        # Do an initial render to populate the cache with real content
        with patch.object(plugin, "_text_to_image", return_value=b"\x00"):
            plugin._render("Previous content", 40, "font/test.otf", "black")

        original_cache = plugin._cache.copy()

        # show_help calls _render which would overwrite _cache, but then restores it
        with patch.object(plugin, "_text_to_image", return_value=b"\x00"):
            plugin.show_help()

        # Cache should be restored to the pre-help state
        assert plugin._cache == original_cache

        # hide_help should re-render the original content and clear help flag
        with patch.object(plugin, "_text_to_image", return_value=b"\x00"):
            plugin.hide_help()
        assert plugin.help_showing is False
        assert plugin._cache["text"] == "Previous content"

    def test_help_showing_false_by_default(self, mock_app, font_config):
        """help_showing should be False on a freshly constructed plugin."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        assert plugin.help_showing is False


class TestIPluginRender:
    """Test the render pipeline and caching."""

    def test_render_returns_false_when_not_activated(self, mock_app, font_config):
        """_render should bail out early if plugin is not activated."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        result = plugin._render("hello")
        assert result is False

    def test_render_returns_false_when_no_deck(self, mock_app, font_config):
        """_render should bail if deck is None."""
        mock_app.deck = None
        plugin = _make_minimal_plugin(mock_app, font_config)
        plugin._activated = True
        result = plugin._render("hello")
        assert result is False

    def test_render_updates_cache(self, mock_app, font_config):
        """_render should update the cache dict with the rendered parameters."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        plugin._activated = True

        with patch.object(plugin, "_text_to_image", return_value=b"\x00"):
            result = plugin._render("test text", 40, "font/test.otf", "blue")

        assert result is True
        assert plugin._cache["text"] == "test text"
        assert plugin._cache["font_size"] == 40
        assert plugin._cache["font_path"] == "font/test.otf"
        assert plugin._cache["bg_color"] == "blue"

    def test_render_uses_font_config_defaults(self, mock_app, font_config):
        """_render called with no args should pick up font_size from font config."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        plugin._activated = True

        with patch.object(plugin, "_text_to_image", return_value=b"\x00"):
            plugin._render("text")

        assert plugin._cache["font_size"] == font_config["font_size"]


class TestIPluginWrap:
    """Test the modular wrap helper used for rotary navigation."""

    def test_wrap_forward_past_end(self, mock_app, font_config):
        """Wrapping past the end should cycle to 0."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        assert plugin._wrap(5, 5) == 0
        assert plugin._wrap(6, 5) == 1

    def test_wrap_backward_before_start(self, mock_app, font_config):
        """Wrapping before 0 should cycle to end."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        assert plugin._wrap(-1, 5) == 4
        assert plugin._wrap(-2, 5) == 3

    def test_wrap_zero_length_returns_zero(self, mock_app, font_config):
        """Wrapping with length 0 should return 0 (no crash, no division error)."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        assert plugin._wrap(3, 0) == 0

    def test_wrap_identity_within_range(self, mock_app, font_config):
        """Values already in range should pass through unchanged."""
        plugin = _make_minimal_plugin(mock_app, font_config)
        for i in range(5):
            assert plugin._wrap(i, 5) == i
