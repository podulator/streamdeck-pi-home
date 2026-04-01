"""
Tests for the player type hierarchy (types.py, VlcPlayer).

Covers:
- Artist/Album/Track/Playlist data models: construction, display_name
  formatting (capwords + underscore-to-space), ordering, JSON serialisation
- VlcPlayer: playlist management (enqueue, enqueue_album, shuffle, clear,
  remove), volume clamping, loop mode — all without touching real VLC

We import types directly from their file to avoid triggering the
plugins/__init__.py eager-import chain.
"""
import sys
import types as _types_mod
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _import_player_types():
    """Load plugins.shared.player.types directly, bypassing plugins/__init__.py."""
    import importlib.util

    # Ensure parent packages exist in sys.modules without executing their __init__
    for pkg in ["plugins", "plugins.shared", "plugins.shared.player"]:
        if pkg not in sys.modules:
            sys.modules[pkg] = _types_mod.ModuleType(pkg)

    spec = importlib.util.spec_from_file_location(
        "plugins.shared.player.types",
        _ROOT / "plugins" / "shared" / "player" / "types.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["plugins.shared.player.types"] = mod
    spec.loader.exec_module(mod)
    return mod


def _import_vlc_player():
    """Load plugins.shared.player.vlc_player directly."""
    import importlib.util

    # types must be loaded first
    types_mod = _import_player_types()

    for pkg in ["plugins", "plugins.shared", "plugins.shared.player"]:
        if pkg not in sys.modules:
            sys.modules[pkg] = _types_mod.ModuleType(pkg)

    spec = importlib.util.spec_from_file_location(
        "plugins.shared.player.vlc_player",
        _ROOT / "plugins" / "shared" / "player" / "vlc_player.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["plugins.shared.player.vlc_player"] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load so fixtures can reference the classes
_ptypes = _import_player_types()
Artist = _ptypes.Artist
Album = _ptypes.Album
Track = _ptypes.Track
Playlist = _ptypes.Playlist


# ---------------------------------------------------------------------------
# Type model tests
# ---------------------------------------------------------------------------

class TestArtistModel:
    """Artist data class behaviour."""

    def test_display_name_capitalises_words(self):
        """display_name should apply capwords and replace underscores with spaces."""
        a = Artist("1", "the_beatles")
        assert a.display_name == "The Beatles"

    def test_display_name_mixed_case(self):
        """capwords normalises input regardless of original capitalisation."""
        a = Artist("1", "DAVID BOWIE")
        assert a.display_name == "David Bowie"

    def test_artist_lt_comparison(self):
        """Artists should be orderable by display_name for sorting."""
        a = Artist("1", "zz top")
        b = Artist("2", "abba")
        assert b < a

    def test_albums_default_empty(self):
        """A new Artist has no albums."""
        a = Artist("1", "test")
        assert a.albums == []

    def test_albums_settable(self):
        """Artist.albums should accept a list assignment."""
        a = Artist("1", "test")
        album = Album("a1", "debut", "test", 2000)
        a.albums = [album]
        assert len(a.albums) == 1

    def test_to_json_keys(self):
        """toJSON should contain id, name, num_albums."""
        a = Artist("ar1", "test artist")
        j = a.toJSON()
        assert j["id"] == "ar1"
        assert "name" in j
        assert "num_albums" in j


class TestAlbumModel:
    """Album data class behaviour."""

    def test_display_name_formats_correctly(self):
        """display_name should capwords and replace underscores."""
        al = Album("1", "dark_side_of_the_moon", "Pink Floyd", 1973)
        assert al.display_name == "Dark Side Of The Moon"

    def test_year_stored(self):
        """Year should be accessible via the .year property."""
        al = Album("1", "album", "artist", 1999)
        assert al.year == 1999

    def test_tracks_default_empty(self):
        """A new Album has no tracks."""
        al = Album("1", "album", "artist")
        assert al.tracks == []

    def test_artist_name_stored(self):
        """artist_name property should return the artist arg."""
        al = Album("1", "album", "Pink Floyd", 1973)
        assert al.artist_name == "Pink Floyd"


class TestTrackModel:
    """Track data class behaviour."""

    def test_display_name_capitalised(self):
        """Track display_name should be capwords of the name."""
        t = Track("1", "come_as_you_are", "nevermind", "nirvana", 1)
        assert t.display_name == "Come As You Are"

    def test_url_settable(self):
        """URL should be settable after construction (needed for lazy stream URLs)."""
        t = Track("1", "song", "album", "artist", 1)
        assert t.url == ""
        t.url = "http://example.com/song.mp3"
        assert t.url == "http://example.com/song.mp3"

    def test_lt_comparison_by_index(self):
        """Tracks are ordered by index for playlist ordering."""
        t1 = Track("1", "a", "album", "artist", 1)
        t2 = Track("2", "b", "album", "artist", 2)
        assert t1 < t2

    def test_to_json_contains_all_fields(self):
        """toJSON should contain all expected keys."""
        t = Track("t1", "song", "album", "artist", 3, "http://url")
        j = t.toJSON()
        assert j["id"] == "t1"
        assert j["index"] == 3
        assert j["url"] == "http://url"
        assert "display_name" in j
        assert "artist_name" in j
        assert "album_name" in j


class TestPlaylistModel:
    """Playlist data class behaviour."""

    def test_display_name_formatted(self):
        """display_name should apply capwords and underscore replacement."""
        p = Playlist("p1", "my_favourite_tracks", 10)
        assert p.display_name == "My Favourite Tracks"

    def test_num_tracks_stored(self):
        """num_tracks should be accessible via the property."""
        p = Playlist("p1", "test", 5)
        assert p.num_tracks == 5

    def test_tracks_default_empty(self):
        """A new Playlist has no tracks."""
        p = Playlist("p1", "test")
        assert p.tracks == []


# ---------------------------------------------------------------------------
# VlcPlayer fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def vlc_player_fixture(mock_app):
    """
    Create a VlcPlayer with a mocked VLC backend.
    The background 'now playing' thread is stopped immediately after init.
    """
    vlc_mod = _import_vlc_player()

    mock_instance = MagicMock()
    mock_vlc_player_obj = MagicMock()
    mock_instance.media_player_new.return_value = mock_vlc_player_obj
    mock_vlc_player_obj.event_manager.return_value = MagicMock()

    with patch.object(vlc_mod, "Instance", return_value=mock_instance):
        callback = MagicMock()
        player = vlc_mod.VlcPlayer(mock_app, callback)
        # Kill the background thread immediately — we don't need it for these tests
        player._thread_running = False

    return player, callback, vlc_mod


# ---------------------------------------------------------------------------
# VlcPlayer playlist tests
# ---------------------------------------------------------------------------

class TestVlcPlayerPlaylist:
    """VlcPlayer playlist management without real VLC."""

    def test_enqueue_adds_track(self, vlc_player_fixture):
        """enqueue() should append a track to the playlist."""
        player, cb, _ = vlc_player_fixture
        t = Track("1", "song", "album", "artist", 1, "http://url")
        player.enqueue(t, notify=False)
        assert t in player.playlist
        assert len(player.playlist) == 1

    def test_enqueue_with_notify_fires_info_callback(self, vlc_player_fixture):
        """enqueue(notify=True) should fire an INFO_MESSAGE callback."""
        player, cb, vlc_mod = vlc_player_fixture
        t = Track("1", "song", "album", "artist", 1, "http://url")
        player.enqueue(t, notify=True)
        cb.assert_called()
        assert cb.call_args[0][0] == vlc_mod.VlcPlayerEvents.INFO_MESSAGE

    def test_enqueue_album_adds_all_tracks(self, vlc_player_fixture):
        """enqueue_album() should add all tracks from the album."""
        player, cb, _ = vlc_player_fixture
        tracks = [
            Track(f"t{i}", f"song{i}", "album", "artist", i, f"http://url/{i}")
            for i in range(3)
        ]
        player.enqueue_album("Test Album", tracks)
        assert len(player.playlist) == 3

    def test_clear_empties_playlist(self, vlc_player_fixture):
        """clear() should empty the playlist."""
        player, cb, _ = vlc_player_fixture
        tracks = [Track(f"t{i}", f"s{i}", "al", "ar", i) for i in range(3)]
        for t in tracks:
            player.enqueue(t, notify=False)
        player.clear()
        assert player.playlist == []

    def test_remove_track_by_position(self, vlc_player_fixture):
        """remove_track(pos) should remove the track at that index."""
        player, cb, _ = vlc_player_fixture
        t1 = Track("1", "a", "al", "ar", 1)
        t2 = Track("2", "b", "al", "ar", 2)
        player.enqueue(t1, notify=False)
        player.enqueue(t2, notify=False)
        player.remove_track(0)
        assert t1 not in player.playlist
        assert t2 in player.playlist

    def test_remove_track_out_of_range_is_noop(self, vlc_player_fixture):
        """remove_track with bad index should not raise or corrupt state."""
        player, cb, _ = vlc_player_fixture
        t = Track("1", "song", "album", "artist", 1)
        player.enqueue(t, notify=False)
        player.remove_track(999)  # should not raise
        assert len(player.playlist) == 1

    def test_shuffle_delegates_to_random(self, vlc_player_fixture):
        """shuffle() should pass the playlist to random.shuffle."""
        player, cb, vlc_mod = vlc_player_fixture
        tracks = [Track(f"t{i}", f"s{i}", "al", "ar", i) for i in range(3)]
        for t in tracks:
            player.enqueue(t, notify=False)

        with patch(f"{vlc_mod.__name__}.random.shuffle") as mock_shuffle:
            player.shuffle()

        mock_shuffle.assert_called_once_with(player.playlist)


class TestVlcPlayerVolume:
    """Volume clamping and callback behaviour."""

    def test_volume_clamped_at_max(self, vlc_player_fixture):
        """Volume setter should clamp at 100."""
        player, cb, _ = vlc_player_fixture
        player.volume = 200
        assert player.volume == 100

    def test_volume_clamped_at_min(self, vlc_player_fixture):
        """Volume setter should clamp at 0."""
        player, cb, _ = vlc_player_fixture
        player.volume = -50
        assert player.volume == 0

    def test_volume_change_fires_info_callback(self, vlc_player_fixture):
        """Changing volume should fire INFO_MESSAGE."""
        player, cb, vlc_mod = vlc_player_fixture
        player._volume = 50
        cb.reset_mock()
        player.volume = 75
        cb.assert_called()
        assert cb.call_args[0][0] == vlc_mod.VlcPlayerEvents.INFO_MESSAGE

    def test_same_volume_no_callback(self, vlc_player_fixture):
        """Setting volume to the same value should not fire callback."""
        player, cb, _ = vlc_player_fixture
        player._volume = 80
        cb.reset_mock()
        player.volume = 80
        cb.assert_not_called()


class TestVlcPlayerLoop:
    """Loop mode toggle."""

    def test_loop_defaults_false(self, vlc_player_fixture):
        """Loop should be off by default."""
        player, _, _ = vlc_player_fixture
        assert player.loop is False

    def test_setting_loop_true_persists(self, vlc_player_fixture):
        """Setting loop=True should persist."""
        player, _, _ = vlc_player_fixture
        player.loop = True
        assert player.loop is True

    def test_loop_appends_now_playing_to_playlist(self, vlc_player_fixture):
        """When loop is enabled with a now_playing track, it should re-queue it."""
        player, _, _ = vlc_player_fixture
        track = Track("t1", "song", "album", "artist", 1, "http://url")
        player._now_playing = track
        player.loop = True
        assert track in player.playlist
