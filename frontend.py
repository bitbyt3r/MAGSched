from flask import Flask, jsonify, request, render_template
import datetime
import time

import database

app = Flask(__name__)
cache = {}


@app.route("/")
def root():
    return render_template("index.html")


def get_collection(collection):
    age = cache.get(collection+"-age")
    if (not age) or (time.time() - age > 15):
        if collection == "sessions":
            results = list(database.Session.get())
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


@app.route("/<collection>")
def search(collection):
    results = get_collection(collection)
    if results is not None:
        if not results:
            return jsonify([])
        if collection == "sessions":
            start_time = request.args.get("time_range_start")
            if start_time:
                print(start_time)
                if start_time == "now":
                    start_time = time.time()
                elif start_time.startswith("+"):
                    start_time = time.time() + float(start_time.split("+")[1])
                elif start_time.startswith("-"):
                    start_time = time.time() - float(start_time.split("-")[1])
                print(start_time)
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
            return jsonify([])
        prototype = filtered[0]
        for key in prototype.keys():
            if key in request.args:
                if isinstance(prototype[key], list):
                    print(f"Filtering on {key} in {request.args[key]}")
                    filtered = list(
                        filter(lambda x: request.args.get(key) in x[key], filtered))
                else:
                    print(f"Filtering on {key} == {request.args[key]}")
                    filtered = list(
                        filter(lambda x: x[key] == request.args.get(key), filtered))
        final = list(filtered)
        if collection == "sessions":
            final.sort(key=lambda x: x.get(
                request.args.get("sort", "start_time")))
        else:
            final.sort(key=lambda x: x.get(request.args.get("sort", "name")))
        if request.args.get("reverse", "false").lower() == "true":
            final.reverse()
        final = final[int(request.args.get("offset", 0)):]
        if request.args.get("limit", 10):
            final = final[:int(request.args.get("limit", 10))]
        return jsonify(final)
    else:
        return f"Unknown datatype {collection}", 404


@app.route("/<collection>/<item>")
def retrieve(collection, item):
    results = get_collection(collection)
    if results:
        for result in results:
            if result.id == item:
                return jsonify(result.serialize())
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
    return f"Unknown location {location}", 404
