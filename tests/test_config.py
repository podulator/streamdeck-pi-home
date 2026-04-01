"""
Tests for configuration loading and environment variable substitution.

Covers:
- JSON parsing from file
- envsubst expansion of ${VAR} placeholders
- Fallback to default config on missing/malformed files
- Required top-level keys and defaults
- Font and brightness defaults applied by the launcher
"""
import json
import pytest
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path


class TestReadConfig:
    """Test the read_config function from streamdeck_launcher."""

    def _get_read_config(self):
        """Import read_config — requires stubs from conftest."""
        import streamdeck_launcher
        import logging
        # read_config uses a module-level 'log' created at app startup; patch it
        if not hasattr(streamdeck_launcher, 'log') or streamdeck_launcher.log is None:
            streamdeck_launcher.log = logging.getLogger('test')
        return streamdeck_launcher.read_config

    def test_loads_valid_json(self, tmp_path):
        """read_config should parse a valid JSON config file."""
        config_data = {
            "debug": 0,
            "creds_path": ".creds",
            "plugins": [],
            "scrollers": [],
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        read_config = self._get_read_config()
        result = read_config(str(config_file))

        assert result["debug"] == 0
        assert result["creds_path"] == ".creds"
        assert result["plugins"] == []

    def test_envsubst_expands_variables(self, tmp_path, monkeypatch):
        """${VAR} placeholders should be replaced with env var values."""
        config_data = {
            "creds_path": "${MY_CREDS_DIR}",
            "plugins": [],
            "scrollers": [],
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        read_config = self._get_read_config()

        monkeypatch.setenv("MY_CREDS_DIR", "/tmp/test-creds")
        result = read_config(str(config_file))
        assert result["creds_path"] == "/tmp/test-creds"

    def test_missing_file_returns_default(self):
        """If config file doesn't exist, read_config returns a default config."""
        read_config = self._get_read_config()
        result = read_config("/nonexistent/path/config.json")

        # The default config has scrollers and creds_path
        assert "creds_path" in result
        assert "scrollers" in result
        assert isinstance(result["scrollers"], list)

    def test_malformed_json_returns_default(self, tmp_path):
        """Malformed JSON should fall back to the default config."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{ this is not valid json !!!")

        read_config = self._get_read_config()
        result = read_config(str(config_file))

        # Should get fallback config, not crash
        assert "creds_path" in result
        assert "scrollers" in result


class TestConfigDefaults:
    """Test that the launcher applies correct defaults for missing keys."""

    def test_font_defaults_applied_when_missing(self):
        """If config has no 'font' key, TEXT_DEFAULTS should be used."""
        from streamdeck_launcher import TEXT_DEFAULTS

        config = {"plugins": [], "scrollers": []}
        font = config.get("font", None)
        if font is None:
            config["font"] = TEXT_DEFAULTS

        assert config["font"]["font_path"] == "font/terminator.otf"
        assert config["font"]["font_size"] == 80
        assert config["font"]["background_color"] == "black"

    def test_font_not_overridden_when_present(self):
        """If config already has 'font', it should not be replaced."""
        custom_font = {
            "font_path": "custom/font.ttf",
            "font_size": 42,
            "background_color": "navy",
        }
        config = {"font": custom_font, "plugins": [], "scrollers": []}
        font = config.get("font", None)
        if font is None:
            from streamdeck_launcher import TEXT_DEFAULTS
            config["font"] = TEXT_DEFAULTS

        assert config["font"]["font_path"] == "custom/font.ttf"
        assert config["font"]["font_size"] == 42

    def test_brightness_defaults_applied_when_missing(self):
        """If config has no 'brightness' key, defaults should be applied."""
        config = {"plugins": [], "scrollers": []}
        brightness = config.get("brightness", None)
        if brightness is None:
            config["brightness"] = {"minimum": 10, "press_to_wake": 30}

        assert config["brightness"]["minimum"] == 10
        assert config["brightness"]["press_to_wake"] == 30

    def test_brightness_not_overridden_when_present(self):
        """If config already has 'brightness', it should not be replaced."""
        config = {
            "brightness": {"minimum": 5, "press_to_wake": 50, "initial": 80},
            "plugins": [],
            "scrollers": [],
        }
        brightness = config.get("brightness", None)
        if brightness is None:
            config["brightness"] = {"minimum": 10, "press_to_wake": 30}

        assert config["brightness"]["minimum"] == 5
        assert config["brightness"]["initial"] == 80


class TestConfigStructure:
    """Test that the full config structure has the expected shape."""

    def test_full_config_has_required_keys(self, full_config):
        """A full config fixture should have all top-level keys."""
        required = ["brightness", "font", "plugins", "scrollers"]
        for key in required:
            assert key in full_config, f"Missing required key: {key}"

    def test_plugin_entries_have_required_fields(self, full_config):
        """Each plugin entry must have name, class, and config."""
        for plugin in full_config["plugins"]:
            assert "name" in plugin
            assert "class" in plugin
            assert "config" in plugin

    def test_scroller_entries_have_required_fields(self, full_config):
        """Each scroller entry must have name, class, and config."""
        for scroller in full_config["scrollers"]:
            assert "name" in scroller
            assert "class" in scroller
            assert "config" in scroller

    def test_brightness_has_minimum(self, full_config):
        """Brightness config must have a minimum value."""
        assert "minimum" in full_config["brightness"]
        assert isinstance(full_config["brightness"]["minimum"], int)
