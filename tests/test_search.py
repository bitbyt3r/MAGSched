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
