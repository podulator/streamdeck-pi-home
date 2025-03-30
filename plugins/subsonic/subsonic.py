from collections import defaultdict
from libsonic.connection import API_VERSION
from urllib.parse import urlencode
from ..shared.player.vlc_player import VlcPlayerEvents
from ..shared.player.types import Artist, Album, Track
from ..shared.player.iplayer import IPlayer
import libsonic
import textwrap
import threading
import time

class MySubsonicConnection(libsonic.Connection):

    def __init__(self, baseUrl, username = None, password = None, port = 4040, 
            serverPath = '/rest', appName = 'streamdeck-sonic', apiVersion = API_VERSION, 
            insecure = False, useNetrc = None, legacyAuth = False, useGET = False):

        super().__init__(baseUrl, username, password, port, serverPath, appName, apiVersion, insecure, useNetrc, legacyAuth, useGET)

    def stream_url(self, sid : str, maxBitRate : int = 0, tformat = None, 
                   timeOffset=None, size=None, estimateContentLength=False, converted=False) -> str:

        methodName = 'stream'
        viewName = '%s.view' % methodName
        q = self._getQueryDict({
                'id': sid, 
                'maxBitRate': maxBitRate,
                'format': tformat, 
                'timeOffset': timeOffset, 
                'size': size,
                'estimateContentLength': estimateContentLength,
                'converted': converted
            }
        )

        qdict = self._getBaseQdict()
        qdict.update(q)
        base_url = '%s:%d/%s/%s' % (
            self._baseUrl, 
            self._port, 
            self._serverPath,
            viewName
        )
        return f"{base_url}?{urlencode(qdict)}"

class SubsonicPlugin(IPlayer):

    partition_keys = [ "Latest", "Random", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X-Z", "#" ]
    
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

    def on_dial_pushed(self, deck, dial, state):
        super().on_dial_pushed(deck, dial,state)

        if not state: 
            return
        match dial:
            case 0:
                match self._state:
                    case IPlayer.State.PARTITIONS:
                        # make sure we have artists loaded for this 
                        partition_key = self._partition_keys[self._partition_counter]
                        size = len(self._artists[partition_key])
                        if size > 0:
                            self._artist_counter = 0
                            self._show_artist()
                            self._update_buttons()
                        return
                    case IPlayer.State.ARTISTS:
                        # have we got albums loaded for this artist?
                        partition_key = self._partition_keys[self._partition_counter]
                        partition = self._artists[partition_key]
                        artist = partition[self._artist_counter]

                        if len(artist.albums) == 0:
                            self._log.debug(f"loading albums for : {artist.display_name}")
                            self._render(f"{artist.display_name}\n:- Loading albums...\n")

                            artist.albums = self._get_albums_by_artist(artist)
                            self._log.info(f"Loaded {len(artist.albums)} albums")

                        size = len(artist.albums)
                        if size > 0:
                            self._album_counter = 0
                            self._show_album()
                            self._update_buttons()
                        return
                    case IPlayer.State.ALBUMS:
                        # have we got tracks loaded for this album?
                        partition_key = self._partition_keys[self._partition_counter]
                        partition = self._artists[partition_key]
                        artist :Artist = partition[self._artist_counter]
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
                        partition_key = self._partition_keys[self._partition_counter]
                        partition = self._artists[partition_key]
                        artist = partition[self._artist_counter]
                        album = artist.albums[self._album_counter]
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

    def _get_albums_by_filter(self, filter: str) -> list[Album]:
        self._log.info(f"Loading albums filtered by {filter}")
        results: list[Album] = []
        try:
            returned = self._client.getAlbumList(filter)
            albums = returned["albumList"]
            if albums is None: 
                return results

            for album in albums["album"]:
                year : int = 0
                if "year" in album:
                    year = int(album["year"])
                results.append(Album(album["id"], album["name"], album["artist"], year))
            # sort by display_name, then year
            return sorted(results, key = lambda x: ((x.display_name, x.year)) )
        except Exception as ex:
            self._log.error(ex)
            return results
    
    def _get_albums_by_artist(self, artist : Artist) -> list[Album]:
        self._log.info(f"Loading albums for artist : {artist.display_name}")
        results: list[Album] = []
        try:
            returned = self._client.getArtist(artist.id)
            artist = returned["artist"]
            if artist["albumCount"] == 0: 
                return results
            albums = artist["album"]
            if albums is None: 
                return results

            for album in albums:
                year : int = 0
                if "year" in album:
                    year = int(album["year"])
                results.append(Album(album["id"], album["name"], artist["name"], year))
            # sort by display_name, then year
            return sorted(results, key = lambda x: ((x.display_name, x.year)) )
        except Exception as ex:
            self._log.error(ex)
            return results

    def _get_tracks_by_album(self, album : Album) -> list[Track]:
        self._log.info(f"Loading tracks for album : {album.display_name}")
        results: list[Track] = []
        try:
            returned = self._client.getAlbum(album.id)
            album = returned["album"]
            if album["songCount"] == 0: 
                return results
            songs = album["song"]
            if songs is None: 
                return results

            for song in songs:
                id = song["id"]
                name = song["title"]
                index : int = 0
                if "track" in song:
                    index = int(song["track"])
                track = Track(id, name, album["name"], album["artist"], index)
                results.append(track)
                self._log(f"Added track: {track}")

            # sort by track index, then display_name if no index
            return sorted(results, key = lambda x: ((x.index, x.display_name)) )
        except Exception as ex:
            self._log.error(ex)
            return results

    def activate(self) -> bool:
        if not super().activate(): 
            return False
        try:
            if not self._config["username"]:
                self._log.error("Credentials are required")
                return False

            if self._client is None:
                try:
                    self._client = MySubsonicConnection(
                        self._config["ip"], 
                        self._config["username"], 
                        self._config["password"], 
                        int(self._config["port"]), 
                        apiVersion="1.16.0"
                    )
                    self._log.info(self._client.getLicense())
                except Exception as ex:
                    self._client = None
                    self._info_callback({
                        "time": 2, 
                        "message": f"Couldn't connect to server\n{ex}", 
                        "keep": True
                    })
                    self._log.error(f"Couldn't connect to server : {ex}")
                    self._activated = False
                    return False

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
                        partition_key = self._partition_keys[self._partition_counter]
                        match partition_key.lower():
                            case "latest":
                                albums: list[Album] = self._get_albums_by_filter("newest")
                                for album in albums:
                                    self._enqueue_album(album)
                                num_albums: int = len(albums)
                                time.sleep(1)
                                self._render(f"Latest:\n{num_albums} enqueued albums...\n")
                            case "random":
                                albums: list[Album] = self._get_albums_by_filter("random")
                                for album in albums:
                                    self._enqueue_album(album)
                                num_albums: int = len(albums)
                                time.sleep(1)
                                self._render(f"Random:\n{num_albums} enqueued albums...\n")
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

    def _build_cache(self) -> defaultdict[:list] :
        partitions = defaultdict(list)
        partition_keys = SubsonicPlugin.partition_keys.copy()
        for k in partition_keys:
            partitions[k] = []

        self._log.info("Loading artists")
        artists = self._client.getArtists()
        artist_partition_list = artists["artists"]["index"]
        counter : int = 0
        for key in partition_keys:
            for artist_partition in artist_partition_list:
                if artist_partition["name"] == key:
                    artist_list = artist_partition["artist"]
                    num_found = len(artist_list)
                    counter += num_found
                    self._log.info(f"Loaded {num_found} artists for {key}*")
                    for artist in artist_list:
                        a = Artist(artist["id"], artist["name"])
                        partitions[key].append(a)
                    continue

        self._log.info(f"Loaded {counter} artists")

        self._artists = partitions
        self._partition_keys = partition_keys

    def _get_stream_for_track(self, track : Track) -> str:
        if self._client is None: 
            return None
        try:
            return self._client.stream_url(track.id)
        except Exception as ex:
            self._log.error(ex)
            return None
