import uuid
import xml.etree.ElementTree as ET
import zoneinfo
from html.parser import HTMLParser

import config

TZ = zoneinfo.ZoneInfo(config.time_zone_name)

EVENT_TAGS = [
    "date", "start", "duration", "room", "slug", "url", "title", "subtitle", "track",
    "type", "language", "abstract", "description", "logo", "persons", "links", "attachments"
]


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def strip_html(text):
    if not text:
        return ""
    parser = _TextExtractor()
    parser.feed(text)
    return "".join(parser.parts)


def make_guid(collection, id):
    return str(uuid.uuid3(uuid.NAMESPACE_URL, f"{config.base_url}/{collection}/{id}"))


def sessions_to_frab(sessions, locations):
    location_lookup = {x.id: x for x in locations}
    schedule = ET.Element("schedule")
    ET.SubElement(schedule, "generator", name="magsched", version="1.0")
    ET.SubElement(schedule, "version").text = "Guidebook"
    conference = ET.SubElement(schedule, "conference")
    for tagname in ["acronym", "title", "start", "end", "days", "timeslot_duration", "time_zone_name", "base_url"]:
        ET.SubElement(conference, tagname).text = getattr(config, tagname)
    days = {}
    for session in sessions:
        local_start = session.start_time.astimezone(TZ)
        day = local_start.strftime("%Y-%m-%d")
        if day not in days:
            days[day] = {
                "date": day,
                "start": local_start.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                "end": local_start.replace(hour=23, minute=45, second=0, microsecond=0).isoformat(),
                "rooms": {}
            }
        description = strip_html(session.description)
        duration = int((session.end_time - session.start_time).total_seconds())
        for location in session.locations:
            if location not in location_lookup:
                print(f"session {session.id} has invalid location {location}")
                continue
            room = days[day]["rooms"].setdefault(location, {
                "id": location,
                "name": location_lookup[location].name,
                "events": []
            })
            room["events"].append({
                "id": session.id,
                "date": local_start.isoformat(),
                "start": local_start.strftime("%H:%M"),
                "duration": f"{duration // 3600}:{(duration % 3600) // 60:02}",
                "room": room["name"],
                "slug": f"{config.acronym}-{session.id}-sess",
                "url": f"{config.base_url}/sessions/{session.id}",
                "title": session.name,
                "track": session.tracks[0] if session.tracks else "",
                "language": "en",
                "abstract": description,
                "description": description,
                "logo": "https://www.magfest.org/assets/logo_magfest_lg.png",
            })
    for idx, day in enumerate(sorted(days.values(), key=lambda x: x['start'])):
        day_tag = ET.SubElement(schedule, "day", date=day['date'], end=day['end'], index=str(idx + 1), start=day['start'])
        for room in day['rooms'].values():
            room_tag = ET.SubElement(day_tag, "room", guid=make_guid("locations", room['id']), name=room['name'])
            for event in room['events']:
                event_tag = ET.SubElement(room_tag, "event", guid=make_guid("sessions", event['id']), id=str(event['id']))
                for tagname in EVENT_TAGS:
                    ET.SubElement(event_tag, tagname).text = event.get(tagname, "")
                recording = ET.SubElement(event_tag, "recording")
                ET.SubElement(recording, "license")
                ET.SubElement(recording, "optout").text = "false"
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(schedule, encoding="unicode")
