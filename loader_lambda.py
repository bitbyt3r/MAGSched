import json
import os
import urllib3
import time
import boto3
from abc import ABC, abstractmethod
from typing import List
import datetime

http = urllib3.PoolManager()
client = boto3.client('s3')

class Collection(ABC):
    data = []

    @abstractmethod
    def deserialize(cls, string: str): pass

    @abstractmethod
    def serialize(self) -> str: pass

    @classmethod
    def get(cls):
        return cls.data

    @classmethod
    def full_update(cls, members):
        cls.data = members

class Track(Collection):
    @classmethod
    def deserialize(cls, string: str):
        data = json.loads(string)
        return cls(
            data.get("id"),
            data.get("name")
        )

    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name
        }

class Location(Collection):
    @classmethod
    def deserialize(cls, string: str):
        data = json.loads(string)
        return cls(
            data.get("id"),
            data.get("name")
        )

    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name
        }

class Session(Collection):
    @classmethod
    def deserialize(cls, string: str):
        data = json.loads(string)
        return cls(
            data.get("id"),
            datetime.datetime.fromisoformat(data.get("start_time")),
            datetime.datetime.fromisoformat(data.get("end_time")),
            data.get("all_day"),
            data.get("name"),
            data.get("description"),
            data.get("locations"),
            data.get("tracks")
        )

    def __init__(
        self,
        id: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        all_day: bool,
        name: str,
        description: str,
        locations: List[str],
        tracks: List[str]
    ):
        self.id = id
        self.start_time = start_time
        self.end_time = end_time
        self.all_day = all_day
        self.name = name
        self.description = description
        self.locations = locations
        self.tracks = tracks
        assert self.start_time.tzinfo is not None and self.start_time.tzinfo.utcoffset(self.start_time) is not None
        assert self.end_time.tzinfo is not None and self.end_time.tzinfo.utcoffset(self.end_time) is not None

    def serialize(self):
        return {
            "id": self.id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "all_day": self.all_day,
            "name": self.name,
            "description": self.description,
            "locations": self.locations,
            "tracks": self.tracks
        }



class Guidebook:
    def __init__(self, apikey, guide):
        self.guide = guide
        self.baseurl = "https://builder.guidebook.com/open-api/v1/"
        self.headers = {
            "Authorization": f"JWT {apikey}"
        }
        self.global_delay = 0.01

    def call(self, method, url, max_retries=10):
        delay = 0.25
        retries = 0
        while True:
            time.sleep(self.global_delay)
            result = http.request(method, url, headers=self.headers)
            print(method, result.status, url)
            if result.status in [200, 201, 204, 400, 401, 403, 404, 405]:
                # These codes indicate a final result to the request, others are ephemeral and need a retry
                return result
            if result.status == 429:
                # Server has asked us to slow down
                self.global_delay = min(self.global_delay*2, 10)
            retries += 1
            if retries > max_retries:
                raise RuntimeError(f"Failed to {method} {url} (got {result.status} after {max_retries} retries)")
            time.sleep(delay)
            delay *= 2

    def list_all(self, path):
        if self.guide:
            next_url = f"{self.baseurl}{path}?guide={self.guide}"
        else:
            next_url = f"{self.baseurl}{path}"
        while next_url:
            result = self.call("GET", next_url)
            if not result.status in [200,]:
                break
            data = json.loads(result.data)
            for item in data.get("results", []):
                yield item
            next_url = data.get("next", None)

    def list_sessions(self):
        for session in self.list_all("sessions"):
            yield Session(
                str(session.get("id")),
                #2017-09-18T22:13:25.766623+0000
                datetime.datetime.strptime(session.get("start_time"), "%Y-%m-%dT%H:%M:%S.%f%z"),
                datetime.datetime.strptime(session.get("end_time"), "%Y-%m-%dT%H:%M:%S.%f%z"),
                session.get("all_day"),
                session.get("name"),
                session.get("description_html"),
                [str(x) for x in session.get("locations")],
                [str(x) for x in session.get("schedule_tracks")]
            )

    def list_locations(self):
        for location in self.list_all("locations"):
            yield Location(
                str(location.get("id")),
                location.get("name")
            )
    
    def list_tracks(self):
        for track in self.list_all("schedule-tracks"):
            yield Track(
                str(track.get("id")),
                track.get("name")
            )

def refresh_cache(sources):
    all_sessions = {}
    all_locations = {}
    all_tracks = {}
    for source in sources:
        sessions = source.list_sessions()
        locations = source.list_locations()
        tracks = source.list_tracks()
        
        for session in sessions:
            all_sessions[session.id] = session

        for location in locations:
            all_locations[location.id] = location

        for track in tracks:
            all_tracks[track.id] = track

    Session.full_update(all_sessions.values())
    Location.full_update(all_locations.values())
    Track.full_update(all_tracks.values())

guidebook = Guidebook(os.environ.get("GUIDEBOOK_API_KEY"), os.environ.get("GUIDEBOOK_GUIDE"))
sources = [guidebook]
update_time = 0
response = ""

def lambda_handler(event, context):
    global update_time
    global response
    if time.time() - update_time > 360 or event.get("action", "") == "refresh":
        refresh_cache(sources)
        update_time = time.time()
        response = json.dumps({
            "sessions": [x.serialize() for x in Session.get()],
            "locations": [x.serialize() for x in Location.get()],
            "tracks": [x.serialize() for x in Track.get()]
        })
        client.put_object(Body=response.encode('UTF-8'), Bucket="magsched-cache", Key="cache.json")
    return {
        'statusCode': 200,
        'body': response
    }
