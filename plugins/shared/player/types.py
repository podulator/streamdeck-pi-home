import json
import string

class Artist():

    key : str = "MusicArtist"

    def __init__(self, id : str, name : str) -> None:
        self._id : str = id
        self._name : str = name
        self._albums : list[Album] = []

    def __lt__(self, other):
        return isinstance(other, Artist) and self.display_name < other.display_name

    def __str__(self) -> str:
        return json.dumps(self.toJSON())

    def toJSON(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "num_albums": len(self.albums)
        }

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name
        
    @property
    def display_name(self):
        return string.capwords(self._name.replace("_", " "))

    @property
    def albums(self) -> list:
        return self._albums

    @albums.setter
    def albums(self, value : list):
        self._albums = value
    
class Album():

    key : str = "MusicAlbum"

    def __init__(self, id : str, name : str, artist: str, year : int = 0) -> None:
        self._id : str = id
        self._name : str = name
        self._artist_name: str = artist
        self._tracks : list[Track] = []
        self._year : int = year

    def __lt__(self, other):
        return isinstance(other, Album) and self.display_name < other.display_name

    def __str__(self) -> str:
        return json.dumps(self.toJSON())

    def toJSON(self) -> dict:
        return {
            "id" : self.id,
            "name" : self.name,
            "artist_name" : self.artist_name,
            "year" : self.year,
            "num_tracks" : len(self.tracks)
        }

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def artist_name(self):
        return self._artist_name

    @property
    def year(self):
        return self._year

    @property
    def display_name(self):
        return string.capwords(self._name.replace("_", " "))

    @property
    def tracks(self) -> list:
        return self._tracks
    
    @tracks.setter
    def tracks(self, value : list):
        self._tracks = value

class Track():

    key : str = "Audio"

    def __init__(self, id : str, name : str, album : str, artist : str, index : int = 0, url : str = "") -> None:
        self._id : str = id
        self._name : str = name
        self._display_name : str = string.capwords(name.replace("_", " "))
        self._artist_name : str = artist
        self._album_name : str = album
        self._index : int = index
        self._url : str = url

    def __lt__(self, other):
        return isinstance(other, Track) and self.index < other.index

    def __str__(self) -> str:
        return json.dumps(self.toJSON())

    def toJSON(self) -> dict:
        return {
            "id" : self.id,
            "name" : self.name,
            "display_name" : self.display_name,
            "artist_name" : self.artist_name,
            "album_name" : self.album_name,
            "index" : self.index,
            "url" : self.url
        }

    @property
    def id(self):
        return self._id

    @property
    def index(self):
        return self._index

    @property
    def name(self):
        return self._name

    @property
    def album_name(self):
        return self._album_name

    @property
    def artist_name(self):
        return self._artist_name

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, value : str):
        self._url = value

    @property
    def display_name(self):
        return self._display_name

    @display_name.setter
    def display_name(self, value : str) -> None:
        self._display_name = string.capwords(value.replace("_", " "))
