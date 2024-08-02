import json
import requests
from Globals import logger

class MalojaApi:
    def __init__(self, url, api_key):
        logger.debug("Trying to log in to Maloja...")
        self.url = url
        self.api_key = api_key
        try:
            self.test_connection()
            logger.info(f"Successfully logged in to Maloja at {self.url}")
        except Exception as e:
            logger.error(f"Error logging in to Maloja: {e}")
        
    def test_connection(self):
        response = requests.get(f"{self.url}/apis/mlj_1/test?key={self.api_key}")
        if response.status_code != 200:
            raise Exception(f"Error testing connection: {response.status_code}, {response.text}")
        
        return response.json()
        
    def submit_scrobble(self, title:str, artists:list[str], album:str = None, album_artists: list[str] = None, duration:int = None, length:int = None, timestamp:int = None):
        data = {
            "artists": artists,
            "title": title,
        }
        if album is not None:
            data["album"] = album
        if album_artists is not None:
            data["albumartists"] = album_artists
        if duration is not None:
            data["duration"] = duration
        if length is not None:
            data["length"] = length
        if timestamp is not None:
            data["time"] = timestamp
            
        response = requests.post(f"{self.url}/apis/mlj_1/newscrobble?key={self.api_key}", json=data)
        if response.status_code != 200:
            raise Exception(f"Error submitting scrobble: {response.status_code}, {response.text}")
        
        # Check if response was json
        if response.headers["Content-Type"] == "application/json":
            try:
                return response.json()
            except:
                pass
            
        return response.text
        
    
    def get_last_scrobbles(self):
        data = {
            "page": 1,
            "perpage": 10
        }
        response = requests.get(f"{self.url}/apis/mlj_1/scrobbles?key={self.api_key}", json=data)
        if response.status_code != 200:
            raise Exception(f"Error getting last scrobbles: {response.status_code}, {response.text}")
    
"""
artists 	List(String) 	Track artists
title 	String 	Track title
album 	String 	Name of the album (Optional)
albumartists 	List(String) 	Album artists (Optional)
duration 	Integer 	How long the song was listened to in seconds (Optional)
length 	Integer 	Actual length of the full song in seconds (Optional)
time 	Integer 	Timestamp of the listen if it was not at the time of submitting (Optional)
nofix 	Boolean 	Skip server-side metadata fixing (Optional)
"""
# POST to self.url/newscrobble
"""
GET /apis/mlj_1/scrobbles 
title 	string 	Track title
artist 	string 	Track artist. Can be specified multiple times.
associated 	bool 	Whether to include associated artists.
from 	string 	Start of the desired time range. Can also be called since or start. Possible formats include '2022', '2022/08', '2022/08/01', '2022/W42', 'today', 'thismonth', 'monday', 'august'
until 	string 	End of the desired range. Can also be called to or end. Possible formats include '2022', '2022/08', '2022/08/01', '2022/W42', 'today', 'thismonth', 'monday', 'august'
in 	string 	Desired range. Can also be called within or during. Possible formats include '2022', '2022/08', '2022/08/01', '2022/W42', 'today', 'thismonth', 'monday', 'august'
page 	int 	Page to show
perpage 	int 	Entries per page.
max 	int 	Legacy. Show first page with this many entries.
Return value
(Dictionary) list (List) 
"""
