import time

import frontend


def test_parse_time():
    now = time.time()
    assert abs(frontend.parse_time("now") - now) < 2
    assert abs(frontend.parse_time("+3600") - (now + 3600)) < 2
    assert abs(frontend.parse_time(" 3600") - (now + 3600)) < 2
    assert abs(frontend.parse_time("-3600") - (now - 3600)) < 2
    assert frontend.parse_time("1700000000") == 1700000000
    assert frontend.parse_time(None) is None
    assert frontend.parse_time("") is None


def test_default_limit(client):
    assert len(client.get("/sessions").json) == 10


def test_limit_all(client):
    assert len(client.get("/sessions?limit=-1").json) == 17


def test_list_filter(client):
    ids = {x["id"] for x in client.get("/sessions?limit=-1&locations=loc2").json}
    assert ids == {"13", "16", "abc-17"}


def test_bool_filter(client):
    ids = {x["id"] for x in client.get("/sessions?limit=-1&all_day=true").json}
    assert ids == {"13"}


def test_exact_filter(client):
    results = client.get("/sessions?limit=-1&name=Marathon").json
    assert [x["id"] for x in results] == ["16"]


def test_time_range_epoch(client):
    # 2026-01-23T00:00:00-05:00 == 1769144400
    ids = {x["id"] for x in client.get("/sessions?limit=-1&time_range_start=1769144400").json}
    assert ids == {"13", "14", "15", "abc-17"}
    ids = {x["id"] for x in client.get("/sessions?limit=-1&time_range_end=1769144400").json}
    assert ids == {str(n) for n in range(1, 13)}


def test_sort_reverse_offset(client):
    names = [x["name"] for x in client.get("/locations?limit=-1").json]
    assert names == ["Main Stage", "Panels 1"]
    names = [x["name"] for x in client.get("/locations?limit=-1&reverse=true").json]
    assert names == ["Panels 1", "Main Stage"]
    names = [x["name"] for x in client.get("/locations?limit=-1&offset=1").json]
    assert names == ["Panels 1"]


def test_description_stripped(client):
    results = client.get("/sessions?limit=-1&id=1").json
    assert results[0]["description"] == "Description 1"


def test_null_description(client):
    results = client.get("/sessions?limit=-1&id=13").json
    assert results[0]["description"] == ""


def test_cache_not_mutated_by_frab(client):
    before = [x["id"] for x in client.get("/sessions?limit=-1&sort=id").json]
    client.get("/frab")
    assert [x["id"] for x in client.get("/sessions?limit=-1&sort=id").json] == before


def test_time_loop_offset(monkeypatch):
    import datetime
    import json

    import config
    import frontend
    import models

    with open(__file__.replace("test_search.py", "fixture_cache.json")) as f:
        data = json.load(f)

    cycle = datetime.timedelta(days=2)  # fixture spans 29h, rounded up to whole days
    starts = {}
    for offset in [0, -86400]:
        monkeypatch.setattr(config, "time_loop_offset", offset)
        sessions = [models.Session.extract(x) for x in data["sessions"]]
        frontend.shift_onto_now(sessions)
        starts[offset] = min(x.start_time for x in sessions)
        # The real clock always lands inside the shifted cycle window
        now = datetime.datetime.now(datetime.UTC)
        assert datetime.timedelta(0) <= now - starts[offset] < cycle
    # A negative offset rewinds the replay: the schedule shifts later by exactly
    # that amount, modulo whole cycles
    assert (starts[0] - starts[-86400] - datetime.timedelta(seconds=-86400)) % cycle == datetime.timedelta(0)
