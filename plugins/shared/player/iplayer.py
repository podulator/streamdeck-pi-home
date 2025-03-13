from collections import defaultdict
from enum import auto, IntEnum
from ...IPlugin import IPlugin
from .types import Artist, Album, Track
from .vlc_player import VlcPlayer, VlcPlayerEvents

import logging
import os
import textwrap
import threading
import time

class IPlayer(IPlugin):

    class State(IntEnum):
        NONE = 0
        PARTITIONS = auto()
        ARTISTS = auto()
        ALBUMS = auto()
        TRACKS = auto()
        PLAYLIST = auto()

    class ToggleState(IntEnum):
        NONE = 0
        SHOW_CURRENT_TRACK = auto()
        SHOW_NEXT_TRACK = auto()
        INFO_LATCH = auto()
        CLEAR_PLAYLIST = auto()
        CLEAR_CACHE = auto()

    class Buttons(IntEnum):
        BACK = 0
        ARTISTS = auto()
        LOOP = auto()
        SHUFFLE = auto()
        ADD = auto()
        STOP = auto()
        PLAY = auto()
        NEXT = auto()

    class ImageKeys(IntEnum):
        ARTIST = 0
        ALBUM = auto()
        TRACK = auto()
        LOOP_ON = auto()
        LOOP_OFF = auto()
        SHUFFLE = auto()
        ADD = auto()
        STOP = auto()
        PLAY = auto()
        PLAYING = auto()
        PAUSED = auto()
        NEXT = auto()

    image_keys = [ "artist.png", "album.png", "track.png", "loop-on.png", "loop-off.png", "shuffle.png", "add.png", "stop.png", "play.png", "playing.png", "paused.png", "next.png" ]

    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)

        self._state = IPlayer.State.NONE
        self._toggle_state = IPlayer.ToggleState.NONE
        self._client = None
        self._images : list[bytes] = None
        self._info_latch : bool = True
        self._info_callback_lock : bool = False
        self._thread : threading.Thread = None
        self._running : bool = False
        self._play_next : bool = False
        self._log : logging.Logger = logging.getLogger(__name__)
        self._log.setLevel(os.environ.get("LOGLEVEL", "INFO"))
        self._player = VlcPlayer(
            app, 
            self._player_callback
        )

        # create and pre allocate the partitions
        self._partition_counter : int = 0
        self._artist_counter : int = 0
        self._album_counter : int = 0
        self._track_counter : int = 0
        self._playlist_counter : int = -1
        self._artists : defaultdict[str, Artist] = defaultdict(list)
        self._last_enqueued_track : Track = None
        self._last_enqueued_album : Album = None
        self._last_enqueued_artist : Artist = None

        self._help_message = "Music Player plugin\nBack | Mode | Repeat | Shuffle\nAdd | Stop | Play | Skip"

    def activate(self) -> bool:
        return super().activate()

    def deactivate(self) -> None:
        super().deactivate()
        if not self._player.playing and not self._player.paused:
            self._stop_everything()

    def destroy(self) -> None:
        super().destroy()
        self._stop_everything()

    def run_as_daemon(self) -> None:
        pass

    @property
    def idle(self) -> bool:
        return self._player.idle

    def _player_callback(self, event_type : VlcPlayerEvents, data : dict) -> None:
        if not self._running: 
            return

        message = data["message"]
        keep = data["keep"]
        time = data["time"]
        debug_message = message.replace("\n", ", ").strip()
        self._log.debug(f"{self._class} :: player callback - {debug_message}")

        match event_type:
            case VlcPlayerEvents.NONE:
                pass
            case VlcPlayerEvents.ERROR_OCCURRED:
                self._log.error(data["message"])
                self._state = IPlayer.State.NONE
                self._render(message)
                self._update_buttons()
            case VlcPlayerEvents.OPENING_FILE:
                pass
            case VlcPlayerEvents.PLAYING_MEDIA:
                self._update_buttons()
            case VlcPlayerEvents.PAUSED_MEDIA:
                self._update_buttons()
            case VlcPlayerEvents.STOPPED_MEDIA:
                self._update_buttons()
            case VlcPlayerEvents.MEDIA_ENDED:
                self._play_next = True
                self._update_buttons()
            case VlcPlayerEvents.INFO_MESSAGE:
                try:
                    if self._info_callback_lock: 
                        return
                    self._info_callback_lock = True
                    self._render(message)
                    if not self._info_latch or not keep:
                        # restore our original state
                        timer = threading.Timer(time, self._restore_state)
                        timer.start()
                    else:
                        self._info_callback_lock = False
                except:
                    pass
            case _:
                self._log.error(f"Unknown VLC Player event : {event_type}")

    def on_dial_turned(self, deck, dial, value) -> None:
        super().on_dial_turned(deck, dial, value)

        match dial:
            case 0:
                match self._state:
                    case IPlayer.State.PARTITIONS:
                        self._partition_counter += sorted((-1, value, 1))[1]
                        size : int = len(self._partition_keys)
                        if size > 0:
                            self._partition_counter = self._wrap(self._partition_counter, size)
                            self._show_partition()
                    case IPlayer.State.ARTISTS:
                        self._artist_counter += value
                        partition_key : str = self._partition_keys[self._partition_counter]
                        partition : str = self._artists[partition_key]
                        size : int = len(partition)
                        if size > 0:
                            self._artist_counter = self._wrap(self._artist_counter, size)
                            self._show_artist()
                    case IPlayer.State.ALBUMS:
                        self._album_counter += value
                        partition_key : str = self._partition_keys[self._partition_counter]
                        partition : str = self._artists[partition_key]
                        artist : str = partition[self._artist_counter]
                        size : int = len(artist.albums)
                        if size > 0: 
                            self._album_counter = self._wrap(self._album_counter, size)
                            self._show_album()
                    case IPlayer.State.TRACKS:
                        self._track_counter += value
                        partition_key : str = self._partition_keys[self._partition_counter]
                        partition : str = self._artists[partition_key]
                        artist : str = partition[self._artist_counter]
                        album : str = artist.albums[self._album_counter]
                        size : int = len(album.tracks)
                        if size > 0: 
                            self._track_counter = self._wrap(self._track_counter, size)
                            self._show_track()
                    case _:
                        return
            case 1:
                value : int = sorted((-1, value, 1))[1]
                new_state : int = self._toggle_state + value
                new_state = self._wrap(new_state, len(IPlayer.ToggleState))
                if 0 == new_state:
                    new_state = 1 if value == 1 else len(IPlayer.ToggleState) - 1
                self._toggle_state = IPlayer.ToggleState(new_state)
                self._show_toggle_state()
                return
            case 2:
                if self._state != IPlayer.State.PLAYLIST: 
                    return
                if self._playlist_counter < 0:                
                    self._playlist_counter = 0
                else:
                    value : int = sorted((-1, value, 1))[1]
                    self._playlist_counter += value
                self._playlist_counter = self._wrap(
                    self._playlist_counter, 
                    len(self._player.playlist)
                )
                self._show_playlist()
            case 3:
                self._player.volume = max(min(100, self._player.volume + value), 0)
            case _:
                return

    def _stop_everything(self) -> None:
        try:
            self._running = False
            self._player.stop()
            self._player.clear()
            self._player.destroy()
            if self._thread is not None:
                self._thread.join()
                self._thread = None
        except:
            pass

    def _run(self) -> None:
        self._log.info(f"{self._class} thread starting")
        while (self._running):
            time.sleep(0.1)
            if self._play_next:
                self._play_next = False
                if len(self._player.playlist) > 0:
                    self._player.play()
        self._log.info(f"{self._class} thread exiting")

    def _restore_state(self) -> None:
        if not self._activated: return
        self._info_callback_lock = False
        if self._info_latch and self._player.playing:
            self._player.show_now_playing()
        else:
            match self._state:
                case IPlayer.State.TRACKS:
                    self._show_track()
                case IPlayer.State.ALBUMS:
                    self._show_album()
                case IPlayer.State.ARTISTS:
                    self._show_artist()
                case IPlayer.State.PARTITIONS:
                    self._show_partition()
                case IPlayer.State.NONE:
                    self._show_partition()
                case _:
                    # playlist
                    pass

        self._update_buttons()

    def _update_buttons(self) -> None:
        if not self._activated: return
        try:

            self._app.set_button_image(IPlayer.Buttons.SHUFFLE, self._images[IPlayer.ImageKeys.SHUFFLE])
            self._app.set_button_image(IPlayer.Buttons.ADD, self._images[IPlayer.ImageKeys.ADD])
            self._app.set_button_image(IPlayer.Buttons.STOP, self._images[IPlayer.ImageKeys.STOP])
            self._app.set_button_image(IPlayer.Buttons.NEXT, self._images[IPlayer.ImageKeys.NEXT])

            match self._state:
                case IPlayer.State.NONE:
                    pass
                case IPlayer.State.PARTITIONS:
                    self._app.set_button_image(IPlayer.Buttons.ARTISTS, self._images[IPlayer.ImageKeys.ARTIST])
                case IPlayer.State.ARTISTS:
                    self._app.set_button_image(IPlayer.Buttons.ARTISTS, self._images[IPlayer.ImageKeys.ARTIST])
                case IPlayer.State.ALBUMS:
                    self._app.set_button_image(IPlayer.Buttons.ARTISTS, self._images[IPlayer.ImageKeys.ALBUM])
                case IPlayer.State.TRACKS:
                    self._app.set_button_image(IPlayer.Buttons.ARTISTS, self._images[IPlayer.ImageKeys.TRACK])

            # toggle loop button
            if self._player.loop:
                self._app.set_button_image(IPlayer.Buttons.LOOP, self._images[IPlayer.ImageKeys.LOOP_ON])
            else:
                self._app.set_button_image(IPlayer.Buttons.LOOP, self._images[IPlayer.ImageKeys.LOOP_OFF])

            # stopped, paused or playing
            if self._player.playing:
                self._app.set_button_image(IPlayer.Buttons.PLAY, self._images[IPlayer.ImageKeys.PLAYING])
            elif self._player.paused:
                self._app.set_button_image(IPlayer.Buttons.PLAY, self._images[IPlayer.ImageKeys.PAUSED])
            else:
                self._app.set_button_image(IPlayer.Buttons.PLAY, self._images[IPlayer.ImageKeys.PLAY])

        except Exception as ex:
            self._log.error(ex)
            pass

    def _show_partition(self) -> None:
        try:
            self._state = IPlayer.State.PARTITIONS
            partition_key = self._partition_keys[self._partition_counter]
            self._log.debug(f"Showing partition : {partition_key}")
            self._render(f"{partition_key}")
        except:
            pass

    def _show_artist(self) -> None:
        try:
            self._state = IPlayer.State.ARTISTS
            partition_key = self._partition_keys[self._partition_counter]
            artist : Artist = self._artists[partition_key][self._artist_counter]

            self._log.debug(f"show_artist :: {artist.display_name}")
            self._render(f"{artist.display_name}\n\n")
        except:
            pass

    def _show_album(self) -> None:
        try:
            self._state = IPlayer.State.ALBUMS
            partition_key = self._partition_keys[self._partition_counter]
            artist : Artist = self._artists[partition_key][self._artist_counter]
            album : Album = artist.albums[self._album_counter]

            self._log.debug(f"show_album :: {album.display_name}")
            msg : str = textwrap.dedent(f"""\
                {artist.display_name}
                :- {self._album_counter + 1} - {album.display_name}
                """
            )
            self._render(msg)
        except Exception as ex:
            self._log.error(ex)
            pass

    def _show_track(self) -> None:
        try:
            self._state = IPlayer.State.TRACKS
            partition_key = self._partition_keys[self._partition_counter]
            artist : Artist = self._artists[partition_key][self._artist_counter]
            album : Album = artist.albums[self._album_counter]
            track : Track = album.tracks[self._track_counter]

            msg : str = textwrap.dedent(f"""\
                {artist.display_name}
                :- {self._album_counter + 1} - {album.display_name}
                 :- {self._track_counter + 1} - {track.display_name}"""
            )
            self._render(msg)
        except:
            pass

    def _show_toggle_state(self) -> None:
        try:
            match self._toggle_state:
                case IPlayer.ToggleState.NONE:
                    return
                case IPlayer.ToggleState.SHOW_CURRENT_TRACK:
                    self._render("Show current track", self._font["font_size"] / 2)
                case IPlayer.ToggleState.SHOW_NEXT_TRACK:
                    self._render("Show next track", self._font["font_size"] / 2)
                case IPlayer.ToggleState.INFO_LATCH:
                    self._render(f"Info latch {'on' if self._info_latch else 'off'}", self._font["font_size"] / 2)
                case IPlayer.ToggleState.CLEAR_PLAYLIST:
                    self._render("Clear playlist", self._font["font_size"] / 2)
                case IPlayer.ToggleState.CLEAR_CACHE:
                    self._render("Clear cache", self._font["font_size"] / 2)
        except Exception as ex:
            self._log.error(ex)

    def _show_playlist(self) -> None:
        try:
            track = self._player.playlist[self._playlist_counter]
            size = len(self._player.playlist)
            self._player_callback(
                VlcPlayerEvents.INFO_MESSAGE, 
                {
                    "time": 0.5, 
                    "message": f"Playlist\n({self._playlist_counter + 1}/{size}) : {track.display_name}", 
                    "keep": True
                }
            )
        except:
            pass

    def _enqueue(self, track : Track) -> None:
        if self._last_enqueued_track == track:
            self._last_enqueued_track = None
            return
        try:
            if not track.url:
                track.url = self._get_stream_for_track(track)
            self._player.enqueue(track)
            self._last_enqueued_track = track
        except Exception as ex:
            self._log.error(ex)

    def _enqueue_album(self, album : Album) -> None:
        if self._last_enqueued_album == album:
            self._last_enqueued_album = None
            return
        try:
            tracks = self._get_tracks_by_album(album)
            for track in tracks:
                if not track.url:
                    track.url = self._get_stream_for_track(track)
            self._player.enqueue_album(album.display_name, tracks)
            self._last_enqueued_album = album
        except Exception as ex:
            self._log.error(ex)

    def _enqueue_artist(self, artist : Artist) -> None:
        if self._last_enqueued_artist == artist:
            self._last_enqueued_artist = None
            return
        try:
            albums = self._get_albums_by_artist(artist)
            for album in albums:
                self._enqueue_album(album)
            self._last_enqueued_artist = artist
        except Exception as ex:
            self._log.error(ex)
