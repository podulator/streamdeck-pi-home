# Test Suite

Interface-focused unit tests for `streamdeck-pi-home`.

## Philosophy

- **Quality over coverage** — tests verify observable behaviour, not internal wiring
- **Mocked hardware** — Stream Deck, VLC, NFC, and PIL are all stubbed; no hardware required
- **Interface focus** — tests target the four key contracts: `IPlugin`, `IScroller`, `IPlayer`/`VlcPlayer`, and config loading

## Running

```bash
# Quickest — uses the helper script (sets up venv if needed)
./run_tests.sh

# Or directly if you have the venv already active
pytest tests/

# Verbose output
pytest tests/ -v

# One specific file
pytest tests/test_plugin_interface.py -v
```

## Test Files

| File | What it tests |
|------|---------------|
| `test_plugin_interface.py` | `IPlugin` contract: lifecycle (init/activate/deactivate), help overlay, render caching, `_wrap` |
| `test_scroller_interface.py` | `IScroller` contract: page lifecycle, `has_next`/`next`/`generate`, `ScrollerFactory` fallback |
| `test_player.py` | `Artist`/`Album`/`Track`/`Playlist` data models; `VlcPlayer` playlist ops, volume clamping, loop mode |
| `test_config.py` | Config loading: valid JSON, `envsubst` expansion, missing file fallback, malformed JSON fallback |
| `test_app.py` | `App`: emergency shutdown bitmask, plugin activate/deactivate, dim-wake, scroller cycling, NFC routing |

## Fixtures (conftest.py)

| Fixture | Description |
|---------|-------------|
| `mock_deck` | Fake Stream Deck + with realistic constants (KEY_COUNT=8, touchscreen dimensions) |
| `mock_app` | Mock App satisfying IPlugin/IScroller constructor requirements |
| `font_config` | Standard font dict matching config.json structure |
| `plugin_config` | Minimal plugin config entry |
| `scroller_config` | Minimal scroller config entry |
| `full_config` | Complete config dict with all top-level keys |
| `sample_artists` | Pre-built Artist → Album → Track hierarchy for player tests |

## Dependencies

Only `pytest` is required (plus the project's own stdlib dependencies).
No extra test libraries — all mocking uses `unittest.mock` from the standard library.

```bash
pip install -r requirements-test.txt
```
