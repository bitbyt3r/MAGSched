import xml.etree.ElementTree as ET


def parse(response):
    assert response.status_code == 200
    assert response.mimetype == "text/xml"
    return ET.fromstring(response.text)


def test_frab_local_generation(client):
    # With CACHE_FILE set (no S3), /frab generates the XML directly
    schedule = parse(client.get("/frab"))
    assert schedule.find("conference/acronym").text == "super2026"
    # Sessions with no valid location (14, 15) are excluded
    events = schedule.findall(".//event")
    assert len(events) == 15
    assert len(schedule.findall("day")) == 2
    by_id = {x.get("id"): x for x in events}
    assert by_id["abc-17"].find("slug").text == "super2026-abc-17-sess"
    assert by_id["16"].find("duration").text == "26:00"
    assert by_id["13"].find("description").text is None  # empty text for null description
    assert by_id["1"].find("abstract").text == "Description 1"


def test_frab_filtered_not_truncated(client):
    schedule = parse(client.get("/frab/filtered"))
    assert len(schedule.findall(".//event")) == 15


def test_frab_filtered_by_location(client):
    schedule = parse(client.get("/frab/filtered?locations=loc2"))
    assert {x.get("id") for x in schedule.findall(".//event")} == {"13", "16", "abc-17"}


def test_frab_redirects_to_configured_url(client, monkeypatch):
    import config
    monkeypatch.setattr(config, "frab_url", "https://example.com/frab.xml")
    response = client.get("/frab")
    assert response.status_code == 302
    assert response.headers["Location"] == "https://example.com/frab.xml"


def test_frab_redirects_to_presigned_url(client, monkeypatch):
    import config
    import frontend

    class FakeS3:
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            assert operation == "get_object"
            assert Params == {"Bucket": config.cache_bucket, "Key": config.frab_key}
            return "https://magsched-cache.s3.amazonaws.com/frab.xml?signed"

    monkeypatch.setattr(config, "cache_file", "")
    frontend.cache["s3"] = FakeS3()
    response = client.get("/frab")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("frab.xml?signed")
