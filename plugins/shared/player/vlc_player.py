from enum import Enum
from threading import Thread
from typing import final
from vlc import MediaPlayer, EventManager, EventType, Instance, Media
from vlc import State, Meta, MediaParseFlag
from .types import Track

import logging
import os
import random
import time

@final
class VlcPlayerEvents(Enum):
    NONE = 0
    ERROR_OCCURRED = 1
    OPENING_FILE = 2
    PLAYING_MEDIA = 3
    PAUSED_MEDIA = 4
    STOPPED_MEDIA = 5
    MEDIA_ENDED = 6
    INFO_MESSAGE = 7

class VlcPlayer:

    def __init__(self, app, player_callback) -> None:
        self._app = app
        self._instance : Instance = Instance('')
        self._event_manager : EventManager = None
        self._player : MediaPlayer = None
        self._now_playing : Track = None
        self._playlist : list[Track] = []
        self._volume : int = 100
        self._info_toggle : int = 0
        self._rotation_counter : int = 0
        self._loop : bool = False
        self._player_callback = player_callback
        self._thread_running : bool = False
        self._thread: Thread = Thread(target = self._now_playing_thread_looper)
        self._thread.daemon = True
        self._thread.start()
        self._log : logging.Logger = logging.getLogger(__name__)
        self._log.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    
    # properties
    @property
    def playlist(self) -> list[Track]:
        return self._playlist

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, value : int) -> None:
        value = max(min(100, value), 0)
        if value != self._volume:
            self._volume = value
            if self._player:
                self._player.audio_set_volume(value)
            self._info_callback(f"Volume {value}", 0.5, False)

    @property
    def playing(self) -> bool:
        return (self.state == State.Playing) and not self.paused

    @property
    def paused(self) -> bool:
        return self.state == State.Paused
    
    @property
    def idle(self) -> bool:
        return (self.playing == False) and (self.paused == False)

    @property
    def state(self) -> State:
        if self._player is None:
            return State.NothingSpecial
        return self._player.get_state()

    @property
    def muted(self) -> bool:
        if (self._player is None):
            return False
        return self._player.audio_get_mute()

    @property
    def loop(self) -> bool:
        return self._loop
    
    @loop.setter
    def loop(self, value : bool) -> None:
        self._loop = value
        if self._loop and self._now_playing:
            try:
                _ : int = self.playlist.index(self._now_playing) 
            except ValueError:
                self.playlist.append(self._now_playing)
            except:
                pass
        else:
            try:
                index : int = self.playlist.index(self._now_playing)
                self.playlist.pop(index)
            except:
                pass

    # callbacks
    def _notify(self, event : VlcPlayerEvents, time : int, message : str, keep : bool) -> None:
        """
        Formats our messages and notifies any listeners. 
        Invoked by all our internal event callbacks
        """
        if None != self._player_callback:
            payload = {
                "time": time, 
                "message": message, 
                "keep": keep
            }
            self._player_callback(event, payload)

    def _info_callback(self, msg : str, time : int, keep : bool) -> None:
        self._notify(VlcPlayerEvents.INFO_MESSAGE, time, msg, keep)

    def _open_callback(self, event : VlcPlayerEvents) -> None:
        self._notify(VlcPlayerEvents.OPENING_FILE, 0, "Opening", False)

    def _paused_callback(self, event : VlcPlayerEvents) -> None:
        self._notify(VlcPlayerEvents.PAUSED_MEDIA, 2, "Paused", True)

    def _stopped_callback(self, event : VlcPlayerEvents) -> None:
        self._notify(VlcPlayerEvents.STOPPED_MEDIA, 2, "Stopped", False)

    def _end_callback(self, event : VlcPlayerEvents) -> None:
        self._now_playing = None
        if len(self.playlist) == 0:
            self._notify(VlcPlayerEvents.INFO_MESSAGE, 2, "Playlist empty", True)
        else:
            self._notify(VlcPlayerEvents.MEDIA_ENDED, 2, "Ended", False)
        return

    def _error_callback(self, event : VlcPlayerEvents) -> None:
        self._reset()
        self._now_playing = None
        self._notify(VlcPlayerEvents.ERROR_OCCURRED, 2, f"Error : {event.u}", False)

    def _playing_callback(self, event : VlcPlayerEvents) -> None:
        self._notify(VlcPlayerEvents.PLAYING_MEDIA, 2, "Playing", False)

    def _get_status(self) -> str:

        if self._player is None:
            return "None"

        match self.state:
            case State.Opening:
                return "Opening"
            case State.Buffering:
                return "Buffering"
            case State.NothingSpecial:
                return "NothingSpecial"
            case State.Playing:
                return "Playing"
            case State.Paused:
                return "Paused"
            case State.Stopped:
                return "Stopped"
            case State.Ended:
                return "Ended"
            case _:
                return f"Unknown player state - {self.state}"

    def _reset(self) -> None:
        try:
            self._log.debug("Resetting player")
            self._player.stop()
        except Exception as ex:
            self._log.error(f"Error resetting player : {ex}")

    def _clean_meta(self, payload : str) -> str:
        delims : list[:str] = [ "|", "(", "[", ":" ]
        for d in delims:
            if payload.find(d):
                return payload.split(d)[0]
        return payload

    def _setup_player(self) -> MediaPlayer:
        try:
            self._log.debug("Initialising player for first time")
            player : MediaPlayer = self._instance.media_player_new()
            self._log.debug(f"Setting initial volume to {self._volume}")
            player.audio_set_volume(self._volume)

            # reg cb's
            self._log.debug("Registering callbacks")
            self._event_manager = player.event_manager()
            self._event_manager.event_attach(
                EventType.MediaPlayerOpening,
                self._open_callback
            )
            self._event_manager.event_attach(
                EventType.MediaPlayerPaused,
                self._paused_callback
            )
            self._event_manager.event_attach(
                EventType.MediaPlayerStopped,
                self._stopped_callback
            )
            self._event_manager.event_attach(
                EventType.MediaPlayerEndReached,
                self._end_callback
            )
            self._event_manager.event_attach(
                EventType.MediaPlayerEncounteredError,
                self._error_callback
            )
            self._event_manager.event_attach(
                EventType.MediaPlayerPlaying, 
                self._playing_callback
            )
            self._log.debug("Player initialisation complete")
            return player
        except Exception as ex:
            self._log.error(f"Error initialising player : {ex}")
            self._reset()
            return None

    def _now_playing_thread_looper(self) -> None:
        if self._thread_running: return
        self._thread_running = True
        counter : int = 0
        while self._thread_running:
            time.sleep(1)
            counter += 1
            if counter > 25:
                counter = 0 if self._rotation_counter == 0 else 15
                if self.playing:
                    self.show_now_playing()

    def clear_now_playing(self) -> None:
        if self._now_playing is not None:
            state : State = self.state
            if state == State.Playing or state == State.Paused:
                self._log("Can't clear current song while we are playing")
                return

            if self.loop:
                self.playlist.pop(0)
            self._now_playing = None
            self._info_callback("Song cleared", 2, False)
            self._log.debug("Now playing cleared")

    def play(self, track : Track = None) -> None:
        """
        Plays the next track in the playlist. 
        If a Track is passed in , injects it at the frint and plays it directly. 
        This feature is also used by streaming radio. 
        If the player was in a paused state, it just unpauses it. 
        """

        self._log.debug(f"Play called - {self._get_status()}")
        if self.playing or self.paused:
            self.pause()
            return
        elif len(self.playlist) == 0 and track is None:
            self._log.debug("-> Play called but playlist is empty")
            self._info_callback("Playlist empty", 2, False)
            return

        if track is not None:
            self._log.debug("-> Play called with track, inserting it at front of playlist")
            self.playlist.insert(0, track)

        try :

            if self._player is None:
                self._player = self._setup_player()

            track : Track = self.playlist.pop(0)
            if self.loop:
                self.playlist.append(track)

            self._log.debug(f"Setting media to {track.url}")
            media : Media  = self._instance.media_new(track.url)
            if media is None:
                self._error_callback("Error opening media", 2, False)
                self._reset()
                self._now_playing = None
                return

            self._player.set_media(media)
            self._log.debug(f"Playing track {track.display_name} - ({track.index})")
            result = self._player.play()

            if -1 == result:
                self._error_callback("Error playing track", 2, False)
                self._reset()
                self._now_playing = None
            else:
                self._log.debug("Play was invoked successfully")
                self._now_playing = track
                self._rotation_counter = 0
                self.show_now_playing()

        except Exception as ex:
            self._info_callback("Error playing track", 2, False)
            self._log.error(f"Exception playing : {ex}")
            self._now_playing = None
            self._reset()

    def remove_track(self, position : int) -> None:
        if position < 0 or position >= len(self.playlist): 
            return
        track : Track = self.playlist.pop(position)
        self._info_callback(f"Removed {track.display_name}", 0.5, False)

    def show_playlist_by_index(self, index : int = 0) -> None:
        num_tracks = len(self.playlist)
        if index >= num_tracks: 
            return
        msg = f"{self.playlist[index].display_name} - [{index + 1}/{num_tracks}]"
        self._info_callback(msg, 2, True)

    def show_now_playing(self) -> None:

        if None == self._now_playing: 
            return

        match self._rotation_counter:
            case 0:
                self._info_callback(self._now_playing.display_name, 2, True)
            case 1:
                self._info_callback(f"song: {self._now_playing.display_name}\nalbum: {self._now_playing.album_name}\nartist: {self._now_playing.artist_name}", 2, True)

        self._rotation_counter += 1
        if self._rotation_counter > 1:
            self._rotation_counter = 0

    def enqueue(self, track : Track) -> None:
        if self.loop and self._now_playing is not None:
            try:
                index : int = max(0, self.playlist.index(self._now_playing))
                self.playlist.insert(index, track)
            except:
                self.playlist.append(track)
        else:
            self.playlist.append(track)
        self._log.debug(f"Added track {track.display_name} - ({track.index})")
        self._log.debug(f"Playlist size : {len(self.playlist)}")
        self._info_callback("Added", 0.5, False)

    def enqueue_album(self, name : str, tracks : list[Track]) -> None:
        self.playlist.extend(tracks)
        self._log.debug(f"Added {len(tracks)} tracks to playlist")
        self._info_callback(f"Added album {name}", 0.5, False)

    def shuffle(self) -> None:
        random.shuffle(self.playlist)
        self._info_callback("List shuffled", 0.5, False)

    def clear(self) -> None:
        if len(self.playlist) > 0:
            self.playlist.clear()
            self._info_callback("Playlist cleared", 0.5, False)
        state : State = self.state
        if  state != State.Playing and state != State.Paused:
            self._now_playing = None

    def next(self) -> None:
        self._log.debug(f"Next called - {self._get_status()}")
        self._now_playing = None
        self._reset()
        self.play()

    def stop(self) -> None:
        self._log.debug(f"Stop called - {self._get_status()}")
        if self._player is None:
            return
        elif self.state == State.Stopped:
            self.clear_now_playing()
        else:
            self._reset()
            self._info_callback("Stopped", 2, False)

    def pause(self) -> None:
        self._log.debug(f"Pause called - {self._get_status()}")
        if self._player is None:
            return
        elif self.playing:
            self._log.debug("We're playing so calling pause")
            self._player.pause()
            self._info_callback("Paused", 2.0, True)
        elif self.paused and self._player.get_media() is not None:
            self._log.debug("We're paused and with media, so resuming")
            self._player.pause()
            self._info_callback("Resumed", 1.0, False)

    def toggle_mute(self) -> None:
        if self._player is None:
            return
        elif self._player.audio_get_mute():
            self._player.audio_set_mute(False)
            self._info_callback("Unmuted", 2, False)
        else:
            self._player.audio_set_mute(True)
            self._info_callback("Muted", 2.0, True)
        self._log.debug(f"Mute set to {self._player.audio_get_mute()}")

    def destroy(self) -> None:
        if self._thread is not None:
            self._thread_running = False
            self._thread.join()
            self._thread = None
