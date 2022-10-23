from abc import ABC, abstractmethod
import datetime
import config
import redis
import json

db = redis.Redis(host=config.redis_host, port=config.redis_port, db=config.redis_db, decode_responses=True)

class Collection(ABC):
    @abstractmethod
    def deserialize(cls, string: str): pass

    @abstractmethod
    def serialize(self) -> str: pass

    @classmethod
    def get(cls):
        for member in db.smembers(cls.__name__):
            yield cls.deserialize(member)

    def save(self):
        db.sset(self.__class__.__name__, json.dumps(self.serialize()))

    @classmethod
    def full_update(cls, members):
        with db.pipeline() as pipe:
            pipe.delete(cls.__name__)
            new_members = [json.dumps(x.serialize()) for x in members]
            if new_members:
                pipe.sadd(cls.__name__, *new_members)
            pipe.execute()

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
        locations: list[str],
        tracks: list[str]
    ):
        self.id = id
        self.start_time = start_time
        self.end_time = end_time
        self.all_day = all_day
        self.name = name
        self.description = description
        self.locations = locations
        self.tracks = tracks

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

