from ..shared.player.iplayer import IPlayer
from ..shared.player.types import Artist, Album, Track
from ..shared.player.vlc_player import VlcPlayerEvents
from collections import defaultdict
from jellyfin_apiclient_python import JellyfinClient

import textwrap
import threading

class JellyfinPlugin(IPlayer):

    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)
        # reset everything
        self._state = IPlayer.State.NONE
        self._toggle_state = IPlayer.ToggleState.NONE
        self._info_latch = True
        self._partition_counter = 0
        self._artist_counter = 0
        self._album_counter = 0
        self._track_counter = 0
        self._playlist_counter = -1

    def activate(self) -> bool:
        if not super().activate(): 
            return False
        try:
            if not self._config["username"]:
                self._log.error("Credentials are required")
                self._activated = False
                return False

            if self._client is None:
                try:
                    self._client = JellyfinClient()
                    self._client.config.app('streamdeck', '0.0.1', 'streamdeck', 'jellydeck')
                    self._client.config.data["auth.ssl"] = False
                    self._client.auth.connect_to_address(self._config["ip"])
                    response = self._client.auth.login(
                        self._config["ip"], 
                        self._config["username"], 
                        self._config["password"]
                    )
                    if response is None or response == {}:
                        raise Exception("Login failed")
                except Exception as ex:
                    self._client = None
                    self._player_callback(VlcPlayerEvents.INFO_MESSAGE, {
                        "time": 2, 
                        "message": f"Couldn't connect to server\n{ex}", 
                        "keep": True
                    })
                    self._log.error("Couldn't connect to server : {ex}")
                    self._activated = False
                    return self._activated

            if self._images is None:
                self._images = []
                self._load_images(self._images, IPlayer.image_keys)

            self._update_buttons()

            if len(self._artists.items()) == 0:
                self._build_cache()
            self._restore_state()

            if not self._running:
                self._running = True
                if self._thread is None:
                    self._thread = threading.Thread(target = self._run)
                    self._thread.start()

            self._activated = True

        except Exception as ex:
            self._log.error(ex)
            self._activated = False

        return self._activated

    def on_button_press(self, deck, key, key_state):
        super().on_button_press(deck, key, key_state)

        if not key_state: 
            self._update_buttons()
            return

        match key:
            case IPlayer.Buttons.BACK:
                pass
            case IPlayer.Buttons.ARTISTS:
                if self._state == IPlayer.State.TRACKS:
                    self._track_counter = 0
                    self._show_album()
                elif self._state == IPlayer.State.ALBUMS:
                    self._album_counter = 0
                    self._show_artist()
                else:
                    self._show_partition()
            case IPlayer.Buttons.LOOP:
                self._player.loop = not self._player.loop
            case IPlayer.Buttons.SHUFFLE:
                self._player.shuffle()
            case IPlayer.Buttons.ADD:
                # detect mode and add all tracks at that level
                match self._state:
                    case IPlayer.State.PARTITIONS:
                        pass
                    case IPlayer.State.ARTISTS:
                        partition_key = self._partition_keys[self._partition_counter]
                        artist : Artist = self._artists[partition_key][self._artist_counter]
                        self._enqueue_artist(artist)
                    case IPlayer.State.ALBUMS:
                        partition_key = self._partition_keys[self._partition_counter]
                        artist : Artist = self._artists[partition_key][self._artist_counter]
                        album : Album = artist.albums[self._album_counter]
                        self._enqueue_album(album)
                    case IPlayer.State.TRACKS:
                        partition_key = self._partition_keys[self._partition_counter]
                        artist : Artist = self._artists[partition_key][self._artist_counter]
                        album : Album = artist.albums[self._album_counter]
                        track : Track = album.tracks[self._track_counter]
                        self._enqueue(track)
                    case _:
                        pass
            case IPlayer.Buttons.STOP:
                self._player.stop()
            case IPlayer.Buttons.PLAY:
                if not self._player.playing:
                    self._player.play()
                else: 
                    self._player.pause()
            case IPlayer.Buttons.NEXT:
                self._player.next()

    def on_dial_pushed(self, deck, dial, state):
        super().on_dial_pushed(deck, dial,state)

        if not state: 
            return
        match dial:
            case 0:
                match self._state:
                    case IPlayer.State.PARTITIONS:
                        # make sure we have artists loaded for this 
                        partition_key :str = self._partition_keys[self._partition_counter]
                        if len(self._artists[partition_key]) == 0:
                            self._artists[partition_key] = self._get_artists_by_letter(partition_key)
                            self._log.info(f"Loaded {len(self._artists[partition_key])} artists")

                        size : int = len(self._artists[partition_key])
                        if size > 0:
                            self._artist_counter = 0
                            self._show_artist()
                            self._update_buttons()

                        return
                    case IPlayer.State.ARTISTS:
                        # have we got albums loaded for this artist?
                        partition_key : str = self._partition_keys[self._partition_counter]
                        partition : defaultdict[str, Artist] = self._artists[partition_key]
                        artist : Artist = partition[self._artist_counter]
                        
                        if len(artist.albums) == 0:
                            self._log.debug(f"loading albums for : {artist.display_name}")
                            self._render(f"{artist.display_name}\n:- Loading albums...\n")

                            artist.albums = self._get_albums_by_artist(artist)
                            self._log.info(f"Loaded {len(artist.albums)} albums")

                        size : int = len(artist.albums)
                        if size > 0:
                            self._album_counter = 0
                            self._show_album()
                            self._update_buttons()
                        return
                    case IPlayer.State.ALBUMS:
                        # have we got tracks loaded for this album?
                        partition_key : str = self._partition_keys[self._partition_counter]
                        partition : defaultdict[str, Artist] = self._artists[partition_key]
                        artist : Artist = partition[self._artist_counter]
                        album : Album = artist.albums[self._album_counter]
                        if len(album.tracks) == 0:
                            self._log.debug(f"loading tracks for : {album.display_name}")
                            msg : str = textwrap.dedent(f"""\
                                {artist.display_name}
                                :- {self._album_counter + 1} - {album.display_name}
                                 :- Loading tracks..."""
                            )               
                            self._render(msg)
                            album.tracks = self._get_tracks_by_album(album)
                            self._log.info(f"Loaded {len(album.tracks)} tracks")

                        self._track_counter = 0
                        self._show_track()
                        self._update_buttons()
                        return
                    case IPlayer.State.TRACKS:
                        partition_key : str = self._partition_keys[self._partition_counter]
                        partition  : defaultdict[str, Artist] = self._artists[partition_key]
                        artist : Artist = partition[self._artist_counter]
                        album : Album = artist.albums[self._album_counter]
                        track : Track = album.tracks[self._track_counter]
                        self._enqueue(track)
                        return
                    case _:
                        return
            case 1:
                match self._toggle_state:
                    case IPlayer.ToggleState.NONE:
                        return
                    case IPlayer.ToggleState.INFO_LATCH:
                        self._info_latch = not self._info_latch
                        self._player_callback(VlcPlayerEvents.INFO_MESSAGE, {
                                "time": 1, 
                                "message": f"Info latch {'on' if self._info_latch else 'off'}", 
                                "keep": False
                            }
                        )
                    case IPlayer.ToggleState.CLEAR_CACHE:
                        # we can safely come back to the root partition 
                        self._state = IPlayer.State.PARTITIONS
                        self._build_cache()
                        self._artist_counter = 0
                        self._album_counter = 0
                        self._track_counter = 0
                        self._player_callback(VlcPlayerEvents.INFO_MESSAGE, {
                            "time": 0.5, 
                            "message": "Cache cleared", 
                            "keep": False
                        })
                    case IPlayer.ToggleState.CLEAR_PLAYLIST:
                        self._player.clear()
                    case IPlayer.ToggleState.SHOW_CURRENT_TRACK:
                        self._player.show_now_playing()
                    case IPlayer.ToggleState.SHOW_NEXT_TRACK:
                        self._player.show_playlist_by_index(0)
                    case IPlayer.ToggleState.LOOP:
                        self._player.loop = not self._player.loop
                        self._show_toggle_state()
                self._toggle_state = IPlayer.ToggleState.NONE
                return
            case 2:
                if self._state != IPlayer.State.PLAYLIST:
                    self._playlist_counter = 0
                    self._state = IPlayer.State.PLAYLIST
                else:
                    # remove the current item
                    self._player.remove_track(self._playlist_counter)
                    if self._playlist_counter > len(self._player.playlist):
                        self._playlist_counter = len(self._player.playlist) - 1
                self._show_playlist()
            case 3:
                # volume
                self._player.toggle_mute()
            case _:
                return

    def _build_cache(self):
        self._artists.clear()
        self._partition_keys = []
        for i in range(ord('A'), ord('Z') + 1):
            self._artists[chr(i)] = []
            self._partition_keys.append(chr(i))
        numbers = ord('0')
        self._artists[chr(numbers)] = []
        self._partition_keys.append(chr(numbers))

    def _get_stream_for_track(self, track : Track) -> str:
        if self._client is None: 
            return None
        try:
            return self._client.jellyfin.audio_url(track.id)
        except Exception as ex:
            self._log.error(ex)
            return None

    def _get_artists_by_letter(self, letter: str) -> list[Artist]:
        
        self._log.info(f"Loading artists : {letter}*")

        items = self._client.jellyfin.user_items(
            params={
                'NameStartsWith': letter,
                'Fields': "Id,Name,Type",
                'Recursive': True,
                'IncludeItemTypes': Artist.key, 
                'Limit': 500
            }
        )
        results = []
        if items is None or items["TotalRecordCount"] == 0: 
            return results
        for item in items["Items"]:
            if item["Type"] != Artist.key:
                continue
            results.append(Artist(item["Id"], item["Name"]))
        # sort by display name
        return sorted(results, key = lambda x: x.display_name )

    def _get_albums_by_artist(self, artist : Artist) -> list[Album]:

        self._log.info(f"Loading albums for artist : {artist.display_name}")

        items = self._client.jellyfin.user_items(
            params={
                'ParentId': artist.id,
                'Fields': "Id,Name,ProductionYear,Type",
                'Recursive': True,
                'IncludeItemTypes': Album.key, 
                'Limit': 100
            }
        )
        results = []
        if items is None or items["TotalRecordCount"] == 0: 
            return results
        for item in items["Items"]:
            if item["Type"] != Album.key:
                continue
            year : int = 0
            if "ProductionYear" in item:
                year = int(item["ProductionYear"])
            results.append(Album(item["Id"], item["Name"], year))
        # sort by display_name, then year
        return sorted(results, key = lambda x: ((x.display_name, x.year)) )

    def _get_tracks_by_album(self, album : Album) -> list[Track]:

        self._log.info(f"Loading tracks for album : {album.display_name}")

        items = self._client.jellyfin.user_items(
            params={
                'ParentId': album.id,
                'Fields': "Id,IndexNumber,Name,Type",
                'Recursive': True,
                'IncludeItemTypes': Track.key, 
                'Limit': 50
            }
        )
        results = []
        if items is None or items["TotalRecordCount"] == 0: 
            return results
        for item in items["Items"]:
            if item["Type"] != Track.key:
                continue
            id = item["Id"]
            name = item["Name"]
            index : int = 0
            if "IndexNumber" in item:
                index = int(item["IndexNumber"])
            results.append(Track(id, name, index))

        # sort by track index, then display_name if no index
        return sorted(results, key = lambda x: ((x.index, x.display_name)) )
