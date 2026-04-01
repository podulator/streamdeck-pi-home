"""
Tests for the IScroller interface contract.

Verifies:
- Page lifecycle: generate → has_next → next → exhaustion
- Page counter reset on generate()
- TextScroller as the concrete reference implementation
- ScrollerFactory fallback behaviour for unknown classes

We import the scroller modules directly (bypassing scrollers/__init__.py)
to avoid pulling in yfinance/requests_cache via the stocks scroller.
"""
import sys
import types
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _ensure_scroller_stubs():
    """
    Ensure the scroller sub-packages are importable without their
    heavy transitive deps. The scrollers package __init__.py eagerly
    imports all scrollers (including stocks, which needs requests_cache).
    We pre-register mocks for the ones we don't test directly.
    """
    for mod in [
        "scrollers",
        "scrollers.clock", "scrollers.clock.clock",
        "scrollers.cmd", "scrollers.cmd.cmd",
        "scrollers.date", "scrollers.date.date",
        "scrollers.stocks", "scrollers.stocks.stocks",
        "scrollers.weather", "scrollers.weather.weather",
        # text we load for real below
    ]:
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)


def _load_iscroller():
    """Load IScroller directly from its file, not via the package."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "scrollers.IScroller",
        _ROOT / "scrollers" / "IScroller.py",
    )
    # Pre-register sub-module mocks so IScroller.py's imports don't fail
    _ensure_scroller_stubs()
    mod = importlib.util.module_from_spec(spec)
    sys.modules["scrollers.IScroller"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_text_scroller():
    """Load TextScroller directly."""
    import importlib.util
    _ensure_scroller_stubs()
    _load_iscroller()  # ensure IScroller is loaded first

    spec = importlib.util.spec_from_file_location(
        "scrollers.text.text",
        _ROOT / "scrollers" / "text" / "text.py",
    )
    mod = importlib.util.module_from_spec(spec)
    # scrollers.text package needs a .text attribute pointing at the leaf module
    # because IScroller.create_scroller calls text_scroller.text.TextScroller
    text_pkg = types.ModuleType("scrollers.text")
    text_pkg.text = mod
    sys.modules["scrollers.text"] = text_pkg
    sys.modules["scrollers.text.text"] = mod
    spec.loader.exec_module(mod)
    return mod.TextScroller


@pytest.fixture
def text_scroller(mock_app, font_config):
    """Create a TextScroller with stubbed image loading."""
    TextScroller = _load_text_scroller()
    config = {
        "name": "Test Text",
        "class": "text",
        "config": {
            "lines": ["Line 1", "Line 2", "Line 3"],
        },
    }
    with patch("scrollers.IScroller.IScroller._create_background"):
        return TextScroller(mock_app, config, font_config)


class TestIScrollerPageLifecycle:
    """Verify page iteration: generate, has_next, next."""

    def test_has_next_after_init(self, text_scroller):
        """TextScroller pre-populates pages from config lines, so has_next should be True."""
        assert text_scroller.has_next is True

    def test_next_returns_bytes_and_advances(self, text_scroller):
        """next() should return rendered bytes and advance the page counter."""
        with patch.object(text_scroller, "_render", return_value=b"\xff"):
            first = text_scroller.next()
        assert first is not None
        assert text_scroller._page_counter == 1

    def test_exhaust_pages(self, text_scroller):
        """After consuming all pages, has_next should be False."""
        with patch.object(text_scroller, "_render", return_value=b"\xff"):
            while text_scroller.has_next:
                text_scroller.next()
        assert text_scroller.has_next is False

    def test_next_after_exhaustion_returns_none(self, text_scroller):
        """next() on an exhausted scroller should return None."""
        with patch.object(text_scroller, "_render", return_value=b"\xff"):
            while text_scroller.has_next:
                text_scroller.next()
            result = text_scroller.next()
        assert result is None

    def test_generate_resets_page_counter(self, text_scroller):
        """generate() should reset the page counter and return the first page."""
        with patch.object(text_scroller, "_render", return_value=b"\xff"):
            text_scroller.next()
            text_scroller.next()
            assert text_scroller._page_counter == 2

            result = text_scroller.generate()
        assert result is not None
        # generate() calls next() once internally → counter is 1
        assert text_scroller._page_counter == 1


class TestScrollerProperties:
    """Verify scroller properties are set correctly."""

    def test_name_from_config(self, text_scroller):
        """Scroller name should come from the config dict."""
        assert text_scroller.name == "Test Text"

    def test_pages_populated_from_lines(self, text_scroller):
        """TextScroller should populate _pages from config 'lines'."""
        assert len(text_scroller._pages) == 3
        assert text_scroller._pages[0] == "Line 1"

    def test_deactivate_clears_pages(self, text_scroller):
        """deactivate() should clear the pages list."""
        assert len(text_scroller._pages) > 0
        text_scroller.deactivate()
        assert len(text_scroller._pages) == 0


class TestScrollerFactory:
    """Test the ScrollerFactory dispatch and fallback."""

    def test_factory_creates_text_scroller(self, mock_app, font_config):
        """ScrollerFactory.create_scroller(class='text') should instantiate TextScroller."""
        _ensure_scroller_stubs()
        iscroller_mod = _load_iscroller()
        # Inject a mock TextScroller so the factory dispatch is testable without
        # running real PIL/font code.
        mock_text_cls = MagicMock(name="TextScroller")
        mock_instance = MagicMock()
        mock_text_cls.return_value = mock_instance
        import sys as _sys
        _sys.modules["scrollers.text"].text.TextScroller = mock_text_cls

        config = {"name": "Test", "class": "text", "config": {"lines": ["Hello"]}}
        scroller = iscroller_mod.ScrollerFactory.create_scroller(mock_app, config, font_config)

        mock_text_cls.assert_called_once_with(mock_app, config, font_config)
        assert scroller is mock_instance

    def test_factory_unknown_class_falls_back_to_text(self, mock_app, font_config):
        """Unknown scroller class should fall back to TextScroller with a default config."""
        _ensure_scroller_stubs()
        iscroller_mod = _load_iscroller()
        mock_text_cls = MagicMock(name="TextScroller")
        mock_instance = MagicMock()
        mock_text_cls.return_value = mock_instance
        import sys as _sys
        _sys.modules["scrollers.text"].text.TextScroller = mock_text_cls

        config = {"name": "Bad", "class": "nonexistent_scroller_xyz", "config": {}}
        scroller = iscroller_mod.ScrollerFactory.create_scroller(mock_app, config, font_config)

        # Factory should have called TextScroller (the fallback) once
        assert mock_text_cls.called
        assert scroller is mock_instance
        # The fallback config should indicate an unhandled class
        call_config = mock_text_cls.call_args[0][1]
        assert call_config["class"] == "text"
        # The fallback config text should reference the unhandled class
        fallback_text = str(mock_text_cls.call_args)
        assert "nonexistent_scroller_xyz" in fallback_text
