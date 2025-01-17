import lxml
from bs4 import BeautifulSoup
import boto3
import time
import json
import uuid
import jinja2
import magic
import datetime
import zoneinfo
import pytz
import base64
import os

import database
import config

mime = magic.Magic(mime=True)
env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))
client = boto3.client('s3')
cache = {}

class Request():
    pass
request = Request()

def render_template(path, **kwargs):
    template = env.get_template(path)
    return template.render(**kwargs)

def jsonify(data):
    return json.dumps(data)

def lambda_handler(event, context):
    print(event, context)
    request.args = event.get('queryStringParameters', {})
    request.path = event.get('rawPath', event.get('path'))
    request.method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    body = ""
    status = 200
    encoded = False
    headers = {
        "Content-Type": "application/json"
    }
    
    if request.path == "/":
        body = root()
        headers["Content-Type"] = "text/html"
    elif request.path == "/frab":
        body = frab()
        headers["Content-Type"] = "text/xml"
    elif request.path == "/frab/filtered":
        body = frab_filtered()
        headers["Content-Type"] = "text/xml"
    elif request.path == "/bops-graphics":
        body = bops_graphics()
    elif request.path in ["/sessions", "/locations", "/tracks"]:
        body = search_collection(request.path[1:])
    elif request.path.split("/")[1] in ["sessions", "locations", "tracks"] and len(request.path.split("/")) == 3:
        _, collection, item = request.path.split("/")
        body = retrieve(collection, item)
    elif request.path == "/display":
        body = displaylist()
        headers["Content-Type"] = "text/html"
    elif request.path.startswith("/display/"):
        body = display(request.path.split("/display/")[1])
        headers["Content-Type"] = "text/html"
    elif request.path == "/upnext":
        body = upnextlist()
        headers["Content-Type"] = "text/html"
    elif request.path.startswith("/upnext/"):
        body = upnext(request.path.split("/upnext/")[1])
        headers["Content-Type"] = "text/html"
    elif request.path == "/room":
        body = roomlist()
        headers["Content-Type"] = "text/html"
    elif request.path.startswith("/room/"):
        body = room(request.path.split("/room/")[1])
        headers["Content-Type"] = "text/html"
    elif request.path == "/tvguide":
        body = tvguide()
        headers["Content-Type"] = "text/html"
    elif request.path.startswith("/static/"):
        filename = os.path.join("static", request.path.split("/static/", 1)[1])
        headers["Content-Type"] = mime.from_file(filename)
        with open(filename, "rb") as filehandle:
            body = base64.b64encode(filehandle.read())
        encoded = True
    if not body:
        status = 404
        body = "Not Found. See <a href='/'>the docs</a>"
        headers['Content-Type'] = "text/html"
    
    return {
        'statusCode': status,
        'body': body,
        'headers': headers,
        'isBase64Encoded': encoded
    }
    

def root():
    return render_template("index.html")

def get_collection(collection):
    age = cache.get(collection+"-age")
    if (not age) or (time.time() - age > 15):
        now = time.time()
        data = client.get_object(Bucket="magsched-cache", Key="cache.json")['Body'].read()
        resources = json.loads(data)
        cache['sessions'] = [database.Session.extract(x) for x in resources['sessions']]
        if config.time_loop:
            start = None
            end = None
            for session in cache['sessions']:
                if not start or session.start_time < start:
                    start = session.start_time
                if not end or session.end_time > end:
                    end = session.end_time
            if start and end:
                event_duration = end - start
                time_since_start = datetime.datetime.utcnow().replace(tzinfo=zoneinfo.ZoneInfo('UTC')) - start
                time_offset = event_duration * (time_since_start // event_duration)
                for session in cache['sessions']:
                    session.start_time += time_offset
                    session.end_time += time_offset
        cache['tracks'] = [database.Track.extract(x) for x in resources['tracks']]
        cache['locations'] = [database.Location.extract(x) for x in resources['locations']]
        for collectionname in ["sessions", "tracks", "locations"]:
            cache[collectionname+"-age"] = now
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

def bops_graphics():
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
    return jsonify(formatted)

def search_collection(collection):
    results = search(collection)
    return jsonify(results)

def retrieve(collection, item):
    results = get_collection(collection)
    if results is not None:
        for result in results:
            if result.id == item:
                return jsonify(result.serialize())

def displaylist():
    locations = get_collection("locations")
    return render_template("displaylist.html", locations=locations)

def display(display):
    locations = get_collection("locations")
    for location in locations:
        if location.id == display:
            return render_template("display.html", location=location)

def upnextlist():
    locations = get_collection("locations")
    return render_template("upnextlist.html", locations=locations)

def upnext(display):
    locations = get_collection("locations")
    for location in locations:
        if location.id == display:
            return render_template("upnext.html", location=location)

def roomlist():
    locations = get_collection("locations")
    return render_template("roomlist.html", locations=locations)

def room(display):
    locations = get_collection("locations")
    for location in locations:
        if location.id == display:
            return render_template("room.html", location=location)

def tvguide():
    return render_template("tvguide.html", locations=[])

def make_guid(collection, id):
    url = f"{config.base_url}/{collection}/{id}"
    gid = uuid.uuid3(uuid.NAMESPACE_URL, url)
    return str(gid)

def sessions_to_frab(sessions):
    locations = get_collection("locations")
    location_lookup = {x.id: x for x in locations}
    soup = BeautifulSoup()
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

def frab():
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
    return full_frab

def frab_filtered():
    results = [database.Session.extract(x) for x in search("sessions")]
    return str(sessions_to_frab(results))