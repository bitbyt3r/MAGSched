import datetime
import gzip
import json
import time
import traceback

from flask import Flask, jsonify, make_response, redirect, render_template, request

import config
import models
from frab import TZ, sessions_to_frab, strip_html

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600
cache = {}


COMPRESS_MIN_BYTES = 102400


@app.after_request
def compress_large_responses(response):
    # The ALB in front of the Lambda caps response bodies at 1MB; the full
    # schedule exceeds that, so compress big responses when the client allows it.
    if (
        "gzip" in request.headers.get("Accept-Encoding", "").lower()
        and not response.direct_passthrough
        and (response.content_length or 0) > COMPRESS_MIN_BYTES
        and "Content-Encoding" not in response.headers
    ):
        response.set_data(gzip.compress(response.get_data()))
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Vary"] = "Accept-Encoding"
    return response


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    if response.mimetype == "text/html":
        # Signage boxes must pick up new pages on reload, not heuristically cache them
        response.headers["Cache-Control"] = "no-cache"
    return response


def s3_client():
    if "s3" not in cache:
        import boto3
        cache["s3"] = boto3.client("s3")
    return cache["s3"]


def load_cache():
    if config.cache_file:
        with open(config.cache_file) as filehandle:
            return json.load(filehandle)
    data = s3_client().get_object(Bucket=config.cache_bucket, Key=config.cache_key)['Body'].read()
    return json.loads(data)


def shift_onto_now(sessions):
    """TIME_LOOP: replay the schedule endlessly by shifting it forward onto the current time.

    The cycle length is the schedule's span rounded up to whole days, so shifted
    times keep their real clock time and each real day replays one schedule day.
    """
    if not sessions:
        return
    start = min(x.start_time for x in sessions)
    end = max(x.end_time for x in sessions)
    cycle = datetime.timedelta(days=max(1, -(-(end - start) // datetime.timedelta(days=1))))
    time_offset = cycle * ((datetime.datetime.now(datetime.UTC) - start) // cycle)
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


def xml_response(body):
    response = make_response(body)
    response.mimetype = "text/xml"
    return response


@app.route("/frab")
def frab():
    # The loader pregenerates frab.xml in S3; redirect consumers straight to it.
    if config.frab_url:
        return redirect(config.frab_url)
    if config.cache_file:
        # Local development without S3: generate on the fly.
        sessions = sorted(get_collection("sessions"), key=lambda x: x.start_time)
        return xml_response(sessions_to_frab(sessions, get_collection("locations")))
    url = s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": config.cache_bucket, "Key": config.frab_key},
        ExpiresIn=600,
    )
    return redirect(url)


@app.route("/frab/filtered")
def frab_filtered():
    results = [models.Session.extract(x) for x in search("sessions", default_limit=-1)]
    return xml_response(sessions_to_frab(results, get_collection("locations")))


from apig_wsgi import make_lambda_handler
lambda_handler = make_lambda_handler(app, binary_support=True)
