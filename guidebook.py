import datetime
import time

import requests

import models


class Guidebook:
    def __init__(self, apikey, guide, baseurl="https://builder.guidebook.com/open-api/v1/"):
        if not apikey:
            raise ValueError("A Guidebook API key is required")
        self.guide = guide
        self.baseurl = baseurl
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"JWT {apikey}"
        self.global_delay = 0.01

    def get(self, url, max_retries=10):
        delay = 0.25
        result = None
        for _ in range(max_retries + 1):
            time.sleep(self.global_delay)
            result = self.session.get(url)
            print("GET", result.status_code, url)
            if result.status_code in [200, 201, 204, 400, 401, 403, 404, 405]:
                # These codes are a final result to the request; others are ephemeral and get retried
                return result
            if result.status_code == 429:
                # Server has asked us to slow down
                self.global_delay = min(self.global_delay * 2, 10)
            time.sleep(delay)
            delay *= 2
        raise RuntimeError(f"Failed to GET {url} (got {result.status_code} after {max_retries} retries)")

    def list_all(self, path):
        next_url = f"{self.baseurl}{path}"
        if self.guide:
            next_url += f"?guide={self.guide}"
        while next_url:
            result = self.get(next_url)
            if result.status_code != 200:
                break
            data = result.json()
            yield from data.get("results", [])
            next_url = data.get("next")

    def list_sessions(self):
        for session in self.list_all("sessions"):
            yield models.Session(
                str(session.get("id")),
                # 2017-09-18T22:13:25.766623+0000
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
            yield models.Location(str(location.get("id")), location.get("name"))

    def list_tracks(self):
        for track in self.list_all("schedule-tracks"):
            yield models.Track(str(track.get("id")), track.get("name"))
