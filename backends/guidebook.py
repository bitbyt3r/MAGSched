import datetime
import requests
import time

import database

class Guidebook_Backend():
    def __init__(self, config):
        if config.get("type", None) != "guidebook":
            raise ValueError("Config type must match guidebook for this class to work.")

        self.apikey = config.get("apikey", None)
        if not self.apikey:
            raise ValueError("API Key is required to access guidebook")

        self.guide = config.get("guide", None)
        self.name = config.get("name", "Guidebook")
        self.baseurl = config.get("baseurl", "https://builder.guidebook.com/open-api/v1/")
        self.headers = {
            "Authorization": f"JWT {self.apikey}"
        }
        self.session = requests.Session()
        self.global_delay = 0.01

    def _call(self, method, url, params=None):
        time.sleep(self.global_delay)
        if method == "POST":
            return self.session.post(url, headers=self.headers)
        elif method == "GET":
            return self.session.get(url, headers=self.headers, params=params)
        elif method == "PUT":
            return self.session.put(url, headers=self.headers)
        elif method == "PATCH":
            return self.session.patch(url, headers=self.headers)
        elif method == "DELETE":
            return self.session.delete(url, headers=self.headers)
        else:
            raise NotImplementedError(f"Unsupported http verb {method}")

    def call(self, method, url, max_retries=10, params=None):
        delay = 0.25
        retries = 0
        params = {}
        while True:
            result = self._call(method, url, params)
            print(method, result.status_code, url)
            if result.status_code in [200, 201, 204, 400, 401, 403, 404, 405]:
                # These codes indicate a final result to the request, others are ephemeral and need a retry
                return result
            if result.status_code == 429:
                # Server has asked us to slow down
                self.global_delay = min(self.global_delay*2, 10)
            retries += 1
            if retries > max_retries:
                raise RuntimeError(f"Failed to {method} {url} (got {result.status_code} after {max_retries} retries)")
            time.sleep(delay)
            delay *= 2

    def list_all(self, path):
        if self.guide:
            next_url = f"{self.baseurl}{path}?guide={self.guide}"
        else:
            next_url = f"{self.baseurl}{path}"
        while next_url:
            result = self.call("GET", next_url)
            if not result.status_code in [200,]:
                break
            data = result.json()
            for item in data.get("results", []):
                yield item
            next_url = data.get("next", None)

    def list_sessions(self):
        for session in self.list_all("sessions"):
            yield database.Session(
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
            yield database.Location(
                str(location.get("id")),
                location.get("name")
            )
    
    def list_tracks(self):
        for track in self.list_all("schedule-tracks"):
            yield database.Track(
                str(track.get("id")),
                track.get("name")
            )