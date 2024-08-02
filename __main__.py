import argparse
from pathlib import Path
import threading
import time
from mpris2 import get_players_uri, Player
import dbus
import dbus.mainloop.glib
from gi.repository import GLib
import yaml
import coloredlogs
from MalojaApi import MalojaApi
from Cache import Cache
from Globals import get_unix_timestamp, logger, logging_format

class PlayerMetadata:
    song_id = None
    song_title = ""
    song_artist = ""
    song_album = ""
    song_album_artist = ""
    song_track_number = 0
    song_length = 0
    song_url = ""
    play_percentage = 0
    
    def __init__(self, metadata: dict[str, any], position=0):
        self.song_id = metadata.get("mpris:trackid", None)
        self.song_title = metadata.get("xesam:title", "")
        artists = metadata.get("xesam:artist", "")
        if isinstance(artists, list):
            if  len(artists) > 1:
                self.song_artist = ", ".join(artists)
            else:
                self.song_artist = artists[0]
        else:
            self.song_artist = artists
            
        album_artists = metadata.get("xesam:albumArtist", "")
        if isinstance(album_artists, list):
            if  len(album_artists) > 1:
                self.song_album_artist = ", ".join(album_artists)
            else:
                self.song_album_artist = album_artists[0]
        else:
            self.song_album_artist = album_artists
        
        self.song_url = metadata.get("xesam:url", "")
        self.song_album = metadata.get("xesam:album", "")
        self.song_track_number = metadata.get("xesam:trackNumber", 0)
        self.song_length = metadata.get("mpris:length", 0) / 1000000
        self.play_position = position / 1000000
        self.play_percentage = self.play_position / self.song_length * 100
        
    def uuid(self):
        return hash(f"{self.song_id}{self.song_title}{self.song_artist}{self.song_album}{self.song_album_artist}")
        
    def __str__(self):
        return "Title: {self.song_title}\nArtist: {self.song_artist}\nAlbum: {self.song_album}\nAlbum Artist: {self.song_album_artist}\nTrack Number: {self.song_track_number}\nLength: {self.song_length}".format(self=self)

class MPris2Scrobbler:
    """
    A class that represents a scrobbler for the MPRIS2 protocol.

    This class provides methods to get the metadata of the currently playing track
    and send it to a scrobbling service like Last.fm, libre.fm or maloja.
    """
    _player_uri = None
    _player = None
    _metadata:PlayerMetadata = None
    _last_scrobble:str = ""
    
    api: MalojaApi = None
    cache: Cache = None

    def __init__(self, **kwargs):
        self.api = MalojaApi(kwargs['api_url'], kwargs['api_key'])
        self.cache = Cache()
        self.player = None
        self.player_state = None
        self.connect_to_player(kwargs['player_uri'] if 'player_uri' in kwargs else None)
    
    def connect_to_player(self, player_uri=None):
        """
        Connect to the player with the given URI.
        
        If no URI is given, connect to the first player found.
        """
        for uri in get_players_uri():
            uri = str(uri)
            if player_uri is None:
                player_uri = uri
                break
            elif uri == player_uri:
                break
        self._player_uri = player_uri
        logger.info(f"Listening to events from player: {player_uri}")
        
        self.player = Player(dbus_interface_info={'dbus_uri': player_uri})
        # When this property changes, the org.freedesktop.DBus.Properties.PropertiesChanged signal is emitted with the new value.
        #listen to the signal
        self.player.PropertiesChanged = self.on_properties_changed
        
    def on_properties_changed(self, interface, changed:dict[str, any], invalidated):
        if interface != "org.mpris.MediaPlayer2.Player":
            logger.error(f"Incorrect interface: {interface}")
            return
        if "PlaybackStatus" in changed:
            if changed['PlaybackStatus'] == "Playing":
                self._metadata = PlayerMetadata(self.player.Metadata)
            logger.debug(f"Playback status changed: {changed['PlaybackStatus']}")
        else:
            logger.debug(f"Properties changed: {changed=}, {invalidated=}")
    
    def can_scrobble(self):
        if self._metadata is None:
            return False
        if self._metadata.song_length == 0:
            return False
        if self.player.Position >= self._metadata.song_length / 2:
            return True
        
        return False
            
    def print_debug_dbus_array(self, array):
        for key, value in array.items():
            logger.debug(f"{key}: {value}")
            
    def tick(self, run_event):
        while run_event.is_set():
            if self.player is None or self.player.PlaybackStatus != "Playing":
                time.sleep(0.25)
                continue
            
            self._metadata = PlayerMetadata(self.player.Metadata, self.player.Position)
            if self._metadata.play_percentage >= 50 and self._last_scrobble != self._metadata.uuid():
                self._last_scrobble = self._metadata.uuid()
                result = self.api.submit_scrobble(self._metadata.song_title, [self._metadata.song_artist], self._metadata.song_album, [self._metadata.song_album_artist], self._metadata.play_position, self._metadata.song_length, get_unix_timestamp())
                logger.info(f"Scrobble was submitted!")
                logger.debug(f"Response: {result}")
            elif self._metadata.play_percentage < 50:
                logger.debug(f"Playing: {self._metadata.song_title} by {self._metadata.song_artist} ({self._metadata.play_percentage:.2f}%)")
            else:
                logger.debug(f"Scrobble already submitted for: {self._last_scrobble} - {self._metadata.uuid()}")
            
            time.sleep(0.5)
    

def main():
    parser = argparse.ArgumentParser(
        prog='MPris2Scrobbler',
        description='Scrobble tracks from MPRIS2 media players to Last.fm, libre.fm or maloja',
    )
    parser.add_argument("-c", "--config", dest="config_file", help='config.yaml file path')
    parser.add_argument("--list-players", action="store_true", help="list all active MPRIS2 media players")
    parser.add_argument("--log-level", default="WARN", help="Set the log level")
    args = parser.parse_args()

    if args.list_players:
        coloredlogs.install(level="INFO", logger=logger, fmt=logging_format)
        print("")
        logger.info("Currently active MPRIS2 media players:".upper())
        for p in get_players_uri():
            logger.info(f"\t{p}")
        return
    
    coloredlogs.install(level=args.log_level.upper(), logger=logger, fmt=logging_format)

    # load config
    if args.config_file is None:
        args.config_file = "config.yaml"
    
    if Path(args.config_file).is_file():
        with open(args.config_file, "r") as file:
            config = yaml.safe_load(file)
    else:
        logger.error(f"Config file not found: {args.config_file}")
        return
    
    if 'api_url' not in config or 'api_key' not in config:
        logger.error("The config file is missing the 'api_url' or 'api_key' field")
        return

    run_event = threading.Event()
    run_event.set()
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    scrobbler = MPris2Scrobbler(**config)
    mainloop = GLib.MainLoop()
    
    try:
        update_thread = threading.Thread(target=scrobbler.tick, args=(run_event,))
        update_thread.start()
        mainloop.run()
    except KeyboardInterrupt:
        mainloop.quit()
    except  Exception as e:
        logger.exception(e)
        pass
    finally:
        run_event.clear()
        update_thread.join()
        
if __name__ == "__main__":
    main()