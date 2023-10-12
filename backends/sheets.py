import traceback
import datetime
import zoneinfo
import requests
import time
import json
import os

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import database
import config

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

class Sheets_Backend():
    def __init__(self, config):
        if config.get("type", None) != "sheets":
            raise ValueError("Config type must match sheets for this class to work.")

        self.key = config.get("key")
        if not self.key:
            raise ValueError("An API key is required")
        self.sheet = config.get("sheet")
        if not self.sheet:
            raise ValueError("A Google Sheet ID is required")
        self.credentials = json.loads(config.get("credentials"))
        try:
            creds = Credentials.from_authorized_user_info(json.loads(config.get('token')))
        except:
            creds = None
        self.headers = {
            "authorization": "Bearer "+self.key,
            "accept": "application/json"
        }

        refreshed_creds = database.db.get(f"SHEETS-{self.sheet}")
        if refreshed_creds:
            creds = Credentials.from_authorized_user_info(json.loads(refreshed_creds))

        if not creds or not creds.valid != SCOPES:
            if creds and creds.expired and creds.refresh_token == SCOPES:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_config(self.credentials, SCOPES)
                creds = flow.run_local_server(port=0)
        database.db.set(f"SHEETS-{self.sheet}", creds.to_json())
        print("Google Sheets Creds:")
        print(creds.to_json())

        self.service = build("sheets", "v4", credentials=creds)

    def list_all(self, sheet_range):
        rows = self.service.spreadsheets().values().get(spreadsheetId=self.sheet, range=sheet_range).execute().get("values", [])
        if not rows:
            print(f"SHEETS 0 {sheet_range}")
            return []
        labels = rows[0]
        labels = [x.replace(" ", "_").lower().strip() for x in labels]
        data = rows[1:]
        print(f"SHEETS {len(data)} {sheet_range}")
        for row in data:
            obj = {
                "start_time": "",
                "end_time": "",
                "all_day": "false",
                "name": "",
                "description": "",
                "locations": "",
                "schedule_tracks": ""
            }
            for idx, label in enumerate(labels):
                if idx < len(row):
                    obj[label] = row[idx]
            if not obj.get('id'):
                continue
            yield obj

    def list_sessions(self):
        timezone = zoneinfo.ZoneInfo(config.time_zone)
        for session in self.list_all("Sessions"):
            try:
                yield database.Session(
                    str(session.get("id")),
                    #2017-09-18T22:13:25.766623+0000
                    datetime.datetime.strptime(session.get('start_time'), "%m/%d/%Y %H:%M:%S").replace(tzinfo=timezone),
                    datetime.datetime.strptime(session.get('end_time'), "%m/%d/%Y %H:%M:%S").replace(tzinfo=timezone),
                    session.get("all_day").lower() == "true",
                    session.get("name"),
                    session.get("description"),
                    [str(x) for x in session.get("locations").strip().split(" ")],
                    [str(x) for x in session.get("schedule_tracks").strip().split(" ")]
                )
            except:
                traceback.print_exc()

    def list_locations(self):
        for location in self.list_all("Locations"):
            try:
                yield database.Location(
                    str(location.get("id")),
                    location.get("name")
                )
            except:
                traceback.print_exc()
    
    def list_tracks(self):
        for track in self.list_all("Schedule Tracks"):
            try:
                yield database.Track(
                    str(track.get("id")),
                    track.get("name")
                )
            except:
                traceback.print_exc()
