from flask import Flask, jsonify, request, render_template, make_response
from bs4 import BeautifulSoup
import datetime
import zoneinfo
import time
import uuid
import pytz

import database
import config

app = Flask(__name__)
cache = {}

def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    return response

def _cors(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

@app.route("/")
def root():
    return render_template("index.html")

def get_collection(collection):
    age = cache.get(collection+"-age")
    if (not age) or (time.time() - age > 15):
        if collection == "sessions":
            results = list(database.Session.get())
            if config.time_loop:
                start = None
                end = None
                for result in results:
                    if not start or result.start_time < start:
                        start = result.start_time
                    if not end or result.end_time > end:
                        end = result.end_time
                if start and end:
                    event_duration = end - start
                    time_since_start = datetime.datetime.utcnow().replace(tzinfo=zoneinfo.ZoneInfo('UTC')) - start
                    time_offset = event_duration * (time_since_start // event_duration)
                    for result in results:
                        result.start_time += time_offset
                        result.end_time += time_offset
        elif collection == "tracks":
            results = list(database.Track.get())
        elif collection == "locations":
            results = list(database.Location.get())
        else:
            return None
        cache[collection+"-age"] = time.time()
        cache[collection] = results
        return results
    return cache.get(collection)

def search(collection):
    results = get_collection(collection)
    if results is not None:
        if not results:
            return []
        if collection == "sessions":
            start_time = request.args.get("time_range_start")
            if start_time:
                if start_time == "now":
                    start_time = time.time()
                elif start_time.startswith("+"):
                    start_time = time.time() + float(start_time.split("+")[1])
                elif start_time.startswith("-"):
                    start_time = time.time() - float(start_time.split("-")[1])
                results = list(
                    filter(lambda x: x.start_time.timestamp() >= float(start_time), results))
            end_time = request.args.get("time_range_end")
            if end_time:
                if end_time == "now":
                    end_time = time.time()
                elif end_time.startswith("+"):
                    end_time = time.time() + float(end_time.split("+")[1])
                elif end_time.startswith("-"):
                    end_time = time.time() - float(end_time.split("-")[1])
                results = list(
                    filter(lambda x: x.end_time.timestamp() <= float(end_time), results))
        filtered = [x.serialize() for x in results]
        if not filtered:
            return _cors(jsonify([]))
        prototype = filtered[0]
        for key in prototype.keys():
            if key in request.args:
                if isinstance(prototype[key], list):
                    print(f"Filtering on {key} in {request.args[key]}")
                    filtered = list(
                        filter(lambda x: request.args.get(key) in x[key], filtered))
                elif isinstance(prototype[key], bool):
                    print(f"Filtering on {key} == True")
                    filtered = list(
                        filter(lambda x: x[key] == (request.args.get(key).lower() == "true"), filtered)
                    )
                else:
                    print(f"Filtering on {key} == {request.args[key]}")
                    filtered = list(
                        filter(lambda x: x[key] == request.args.get(key), filtered))
        final = list(filtered)
        if collection == "sessions":
            final.sort(key=lambda x: x.get(
                request.args.get("sort", "start_time")))
            for session in final:
                if "description" in session:
                    session['description'] = BeautifulSoup(session['description']).get_text()
        else:
            final.sort(key=lambda x: x.get(request.args.get("sort", "name")))
        if request.args.get("reverse", "false").lower() == "true":
            final.reverse()
        final = final[int(request.args.get("offset", 0)):]
        limit = int(request.args.get("limit", 10))
        if limit > 0:
            final = final[:limit]
        return final
    return []

@app.route("/bops-graphics", methods=["GET", "OPTIONS"])
def bops_graphics():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    sessions = search("sessions")
    locations = get_collection("locations")
    location_lookup = {x.id: x for x in locations}
    formatted = []
    for session in sessions:
        formatted.append({
            "start_time": datetime.datetime.fromisoformat(session['start_time']).astimezone(pytz.timezone(config.time_zone_name)).strftime("%-I:%M %p"),
            "end_time": datetime.datetime.fromisoformat(session['end_time']).astimezone(pytz.timezone(config.time_zone_name)).strftime("%-I:%M %p"),
            "id": session['id'],
            "location": location_lookup[session['locations'][0]].name,
            "name": session['name'],
        })
    return _cors(jsonify(formatted))

@app.route("/<collection>", methods=["GET", "OPTIONS"])
def search_collection(collection):
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    results = search(collection)
    if results:
        return _cors(jsonify(results))
    else:
        return f"Unknown datatype {collection}", 404


@app.route("/<collection>/<item>", methods=["GET", "OPTIONS"])
def retrieve(collection, item):
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    results = get_collection(collection)
    if results:
        for result in results:
            if result.id == item:
                return _cors(jsonify(result.serialize()))
        return f"Could not find {item} in {collection}", 404
    else:
        return f"Unknown datatype {collection}", 404


@app.route("/display")
def displaylist():
    locations = get_collection("locations")
    return render_template("displaylist.html", locations=locations)


@app.route("/display/<display>")
def display(display):
    locations = get_collection("locations")
    for location in locations:
        if location.id == display:
            return render_template("display.html", location=location)
    return f"Unknown location {display}", 404


@app.route("/upnext")
def upnextlist():
    locations = get_collection("locations")
    return render_template("upnextlist.html", locations=locations)


@app.route("/upnext/<display>")
def upnext(display):
    locations = get_collection("locations")
    for location in locations:
        if location.id == display:
            return render_template("upnext.html", location=location)
    return f"Unknown location {location}", 404

def make_guid(collection, id):
    url = f"{config.base_url}/{collection}/{id}"
    gid = uuid.uuid3(uuid.NAMESPACE_URL, url)
    return str(gid)

def sessions_to_frab(sessions):
    locations = get_collection("locations")
    location_lookup = {x.id: x for x in locations}
    soup = BeautifulSoup(features='xml')
    schedule = soup.new_tag("schedule")
    soup.append(schedule)
    generator = soup.new_tag("generator", attrs={"name": "magsched", "version": "1.0"})
    schedule.append(generator)
    version = soup.new_tag("version")
    schedule.append(version)
    version.string = "Guidebook"
    conference = soup.new_tag("conference")
    schedule.append(conference)
    for tagname in [
        "acronym",
        "title",
        "start",
        "end",
        "days",
        "timeslot_duration",
        "time_zone_name",
        "base_url"
    ]:
        tag = soup.new_tag(tagname)
        conference.append(tag)
        tag.string = getattr(config, tagname)
    days = {}
    for session in sessions:
        day = session.start_time.astimezone(pytz.timezone(config.time_zone_name)).strftime("%Y-%m-%d")
        if not day in days:
            days[day] = {
                "date": day,
                "start": session.start_time.astimezone(pytz.timezone(config.time_zone_name)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                "end": session.start_time.astimezone(pytz.timezone(config.time_zone_name)).replace(hour=23, minute=45, second=0, microsecond=0).isoformat(),
                "rooms": {}
            }
        for location in session.locations:
            if not location in days[day]["rooms"]:
                if not location in location_lookup:
                    print(f"session {session.id} has invalid location {location}")
                    continue
                days[day]["rooms"][location] = {
                    "id": location,
                    "name": location_lookup[location].name,
                    "events": [] 
                }
            duration = (session.end_time - session.start_time).seconds
            days[day]["rooms"][location]["events"].append({
                "id": session.id,
                "date": session.start_time.astimezone(pytz.timezone(config.time_zone_name)).isoformat(),
                "start": session.start_time.astimezone(pytz.timezone(config.time_zone_name)).strftime("%H:%M"),
                "duration": f"{duration // 3600}:{int((duration % 3600)/60):02}",
                "room": location_lookup[location].name,
                "slug": f"{config.acronym}-{int(session.id) % 1000000}-sess",
                "url": f"{config.base_url}/sessions/{session.id}",
                "title": session.name,
                "subtitle": "",
                "track": session.tracks[0] if session.tracks else "",
                "type": "",
                "language": "en",
                "abstract": BeautifulSoup(session.description).get_text(),
                "description": BeautifulSoup(session.description).get_text(),
                "logo": "https://www.magfest.org/assets/logo_magfest_lg.png",
                "persons": "",
                "links": "",
                "attachments": ""
            })
    day_list = list(days.values())
    day_list.sort(key=lambda x: x['start'])
    for idx, day in enumerate(day_list):
        day_tag = soup.new_tag("day", date=day['date'], end=day['end'], index=str(idx+1), start=day['start'])
        schedule.append(day_tag)
        for room in day['rooms'].values():
            room_tag = soup.new_tag("room", guid=make_guid("locations", room['id']))
            room_tag.attrs["name"] = room['name']
            day_tag.append(room_tag)
            for event in room['events']:
                event_tag = soup.new_tag("event", guid=make_guid("sessions", event['id']), id=str(event['id']))
                room_tag.append(event_tag)
                for tagname in [
                    "date",
                    "start",
                    "duration",
                    "room",
                    "slug",
                    "url",
                    "title",
                    "subtitle",
                    "track",
                    "type",
                    "language",
                    "abstract",
                    "description",
                    "logo",
                    "persons",
                    "links",
                    "attachments"
                ]:
                    tag = soup.new_tag(tagname)
                    event_tag.append(tag)
                    tag.string = event.get(tagname, "")
                recording = soup.new_tag("recording")
                event_tag.append(recording)
                license = soup.new_tag("license")
                recording.append(license)
                optout = soup.new_tag("optout")
                recording.append(optout)
                optout.string = "false"
    return soup

@app.route("/frab", methods=["GET", "OPTIONS"])
def frab():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    age = cache.get("frab-age")
    if (not age) or (time.time() - age > 60):
        sessions = get_collection("sessions")
        sessions.sort(key=lambda x: x.start_time)
        soup = sessions_to_frab(sessions)
        full_frab = str(soup)
        cache["frab"] = full_frab
        cache["frab-age"] = time.time()
    else:
        full_frab = cache.get("frab")

    response = _cors(make_response(full_frab))
    response.mimetype = "text/xml"
    return response

@app.route("/frab/filtered", methods=["GET", "OPTIONS"])
def frab_filtered():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    results = search("sessions")
    return _cors(make_response(str(sessions_to_frab(results))))