import base64
import json


def test_root(client):
    assert client.get("/").status_code == 200


def test_retrieve(client):
    response = client.get("/sessions/abc-17")
    assert response.status_code == 200
    assert response.json["name"] == "Weird ID"
    assert client.get("/sessions/zzz").status_code == 404
    assert client.get("/nonsense").status_code == 404
    assert client.get("/nonsense/1").status_code == 404


def test_cors_on_everything(client):
    for path in ["/", "/sessions", "/frab", "/nonsense"]:
        assert client.get(path).headers["Access-Control-Allow-Origin"] == "*"
    preflight = client.options("/sessions")
    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Methods"] == "*"


def test_bops_graphics(client):
    response = client.get("/bops-graphics?limit=-1")
    assert response.status_code == 200
    by_id = {x["id"]: x for x in response.json}
    assert len(by_id) == 17
    assert by_id["1"]["location"] == "Panels 1"
    assert by_id["1"]["start_time"] == "10:00 AM"
    assert by_id["14"]["location"] == ""  # no locations
    assert by_id["15"]["location"] == ""  # unknown location


def test_signage_lists(client):
    for view in ["display", "upnext", "room"]:
        response = client.get(f"/{view}")
        assert f'href="/{view}/loc1"' in response.text


def test_signage_modes(client):
    display = client.get("/display/loc1").text
    assert "Up Next: " in display and "Starting" in display
    assert "/static/magfest-logo.svg" in display
    upnext = client.get("/upnext/loc1").text
    assert "Up Next: " in upnext and "Starting" in upnext
    room = client.get("/room/loc1").text
    assert "Now: " in room and "Started" in room and "sessiondescription" in room
    response = client.get("/display/zzz")
    assert response.status_code == 404
    assert "zzz" in response.text


def test_tvguide(client):
    response = client.get("/tvguide")
    assert response.status_code == 200
    assert "schedule.magfest.net" in response.text


def test_static(client):
    response = client.get("/static/logo.png")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert client.get("/static/guidebook-icon.svg").mimetype == "image/svg+xml"


def make_event(path, query=""):
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": query,
        "headers": {"host": "example.com"},
        "requestContext": {"http": {"method": "GET", "path": path, "sourceIp": "127.0.0.1", "protocol": "HTTP/1.1"}},
        "isBase64Encoded": False,
    }


def test_lambda_handler(client):
    import frontend
    response = frontend.lambda_handler(make_event("/sessions", "limit=2"), None)
    assert response["statusCode"] == 200
    assert len(json.loads(response["body"])) == 2
    # No query string at all must not crash
    response = frontend.lambda_handler(make_event("/sessions"), None)
    assert response["statusCode"] == 200
    # Binary static content comes back base64-encoded
    response = frontend.lambda_handler(make_event("/static/logo.png"), None)
    assert response["statusCode"] == 200
    assert response["isBase64Encoded"]
    assert base64.b64decode(response["body"])[:4] == b"\x89PNG"
