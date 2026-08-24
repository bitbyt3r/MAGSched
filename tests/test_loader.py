import json
import xml.etree.ElementTree as ET

import loader
import models


def load_fixture_models():
    with open(__file__.replace("test_loader.py", "fixture_cache.json")) as f:
        data = json.load(f)
    return (
        [models.Session.extract(x) for x in data["sessions"]],
        [models.Location.extract(x) for x in data["locations"]],
        [models.Track.extract(x) for x in data["tracks"]],
    )


def test_build_outputs():
    sessions, locations, tracks = load_fixture_models()
    cache, xml = loader.build_outputs(sessions, locations, tracks)
    assert len(cache["sessions"]) == 17
    assert len(cache["locations"]) == 2
    assert len(cache["tracks"]) == 1
    # The cache round-trips through the models unchanged
    assert models.Session.extract(cache["sessions"][0]).serialize() == cache["sessions"][0]
    schedule = ET.fromstring(xml)
    assert len(schedule.findall(".//event")) == 15
