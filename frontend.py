import datetime
import json
import time
import traceback
import uuid
import xml.etree.ElementTree as ET
import zoneinfo
from html.parser import HTMLParser

from flask import Flask, jsonify, make_response, render_template, request

import config
import models

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600
cache = {}
TZ = zoneinfo.ZoneInfo(config.time_zone_name)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    return response


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


def load_cache():
    if config.cache_file:
        with open(config.cache_file) as filehandle:
            return json.load(filehandle)
    if "s3" not in cache:
        import boto3
        cache["s3"] = boto3.client("s3")
    data = cache["s3"].get_object(Bucket=config.cache_bucket, Key=config.cache_key)['Body'].read()
    return json.loads(data)


def shift_onto_now(sessions):
    """TIME_LOOP: replay the schedule endlessly by shifting it forward onto the current time."""
    if not sessions:
        return
    start = min(x.start_time for x in sessions)
    end = max(x.end_time for x in sessions)
    event_duration = end - start
    if not event_duration:
        return
    time_since_start = datetime.datetime.now(datetime.UTC) - start
    time_offset = event_duration * (time_since_start // event_duration)
    for session in sessions:
        session.start_time += time_offset
        session.end_time += time_offset


def get_collection(collection):
    if collection not in ("sessions", "locations", "tracks"):
        return None
    if time.time() - cache.get("age", 0) > 15:
        try:
            resources = load_cache()
            sessions = [models.Session.extract(x) for x in resources.get("sessions", [])]
            if config.time_loop:
                shift_onto_now(sessions)
            cache["sessions"] = sessions
            cache["locations"] = [models.Location.extract(x) for x in resources.get("locations", [])]
            cache["tracks"] = [models.Track.extract(x) for x in resources.get("tracks", [])]
        except Exception:
            # Keep serving the previous cache; retry on the next refresh window.
            traceback.print_exc()
        cache["age"] = time.time()
    return cache.get(collection, [])


def parse_time(spec):
    """A time_range argument: epoch seconds, "now", or +/-N seconds relative to now."""
    if not spec:
        return None
    if spec == "now":
        return time.time()
    if spec[0] == " ":  # a leading '+' that URL decoding turned into a space
        spec = "+" + spec[1:]
    if spec[0] in "+-":
        return time.time() + float(spec)
    return float(spec)


def search(collection, default_limit=10):
    results = get_collection(collection)
    if results is None:
        return None
    if collection == "sessions":
        start_time = parse_time(request.args.get("time_range_start"))
        if start_time is not None:
            results = [x for x in results if x.start_time.timestamp() >= start_time]
        end_time = parse_time(request.args.get("time_range_end"))
        if end_time is not None:
            results = [x for x in results if x.end_time.timestamp() <= end_time]
    filtered = [x.serialize() for x in results]
    if not filtered:
        return []
    prototype = filtered[0]
    for key, value in request.args.items():
        if key not in prototype:
            continue
        if isinstance(prototype[key], list):
            filtered = [x for x in filtered if value in x[key]]
        elif isinstance(prototype[key], bool):
            filtered = [x for x in filtered if x[key] == (value.lower() == "true")]
        else:
            filtered = [x for x in filtered if x[key] == value]
    default_sort = "start_time" if collection == "sessions" else "name"
    filtered.sort(key=lambda x: x.get(request.args.get("sort", default_sort)))
    if collection == "sessions":
        for session in filtered:
            session["description"] = strip_html(session["description"])
    if request.args.get("reverse", "false").lower() == "true":
        filtered.reverse()
    filtered = filtered[int(request.args.get("offset", 0)):]
    limit = int(request.args.get("limit", default_limit))
    if limit > 0:
        filtered = filtered[:limit]
    return filtered


@app.route("/")
def root():
    return render_template("index.html")


@app.route("/<collection>")
def search_collection(collection):
    results = search(collection)
    if results is None:
        return f"Unknown datatype {collection}", 404
    return jsonify(results)


@app.route("/<collection>/<item>")
def retrieve(collection, item):
    results = get_collection(collection)
    if results is None:
        return f"Unknown datatype {collection}", 404
    for result in results:
        if result.id == item:
            return jsonify(result.serialize())
    return f"Could not find {item} in {collection}", 404


@app.route("/bops-graphics")
def bops_graphics():
    location_lookup = {x.id: x for x in get_collection("locations")}
    formatted = []
    for session in search("sessions"):
        location = location_lookup.get(session['locations'][0]) if session['locations'] else None
        formatted.append({
            "start_time": datetime.datetime.fromisoformat(session['start_time']).astimezone(TZ).strftime("%-I:%M %p"),
            "end_time": datetime.datetime.fromisoformat(session['end_time']).astimezone(TZ).strftime("%-I:%M %p"),
            "id": session['id'],
            "location": location.name if location else "",
            "name": session['name'],
        })
    return jsonify(formatted)


@app.route("/display")
@app.route("/upnext")
@app.route("/room")
def signage_list():
    view = request.path.strip("/")
    return render_template("viewlist.html", view=view, locations=get_collection("locations"))


@app.route("/display/<display>")
@app.route("/upnext/<display>")
@app.route("/room/<display>")
def signage(display):
    mode = request.path.split("/")[1]
    for location in get_collection("locations"):
        if location.id == display:
            return render_template("signage.html", mode=mode, location=location)
    return f"Unknown location {display}", 404


@app.route("/tvguide")
def tvguide():
    return render_template("tvguide.html", schedule_host=config.base_url.split("//")[-1])


def make_guid(collection, id):
    return str(uuid.uuid3(uuid.NAMESPACE_URL, f"{config.base_url}/{collection}/{id}"))


EVENT_TAGS = [
    "date", "start", "duration", "room", "slug", "url", "title", "subtitle", "track",
    "type", "language", "abstract", "description", "logo", "persons", "links", "attachments"
]


def sessions_to_frab(sessions):
    location_lookup = {x.id: x for x in get_collection("locations")}
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


def xml_response(body):
    response = make_response(body)
    response.mimetype = "text/xml"
    return response


@app.route("/frab")
def frab():
    if time.time() - cache.get("frab-age", 0) > 60:
        sessions = sorted(get_collection("sessions"), key=lambda x: x.start_time)
        cache["frab"] = sessions_to_frab(sessions)
        cache["frab-age"] = time.time()
    return xml_response(cache["frab"])


@app.route("/frab/filtered")
def frab_filtered():
    results = [models.Session.extract(x) for x in search("sessions", default_limit=-1)]
    return xml_response(sessions_to_frab(results))


from apig_wsgi import make_lambda_handler
lambda_handler = make_lambda_handler(app, binary_support=True)
