import json

import config
import frab
from guidebook import Guidebook


def fetch():
    source = Guidebook(config.guidebook_api_key, config.guidebook_guide)
    return list(source.list_sessions()), list(source.list_locations()), list(source.list_tracks())


def build_outputs(sessions, locations, tracks):
    cache = {
        "sessions": [x.serialize() for x in sessions],
        "locations": [x.serialize() for x in locations],
        "tracks": [x.serialize() for x in tracks],
    }
    xml = frab.sessions_to_frab(sorted(sessions, key=lambda x: x.start_time), locations)
    return cache, xml


def lambda_handler(event, context):
    import boto3
    sessions, locations, tracks = fetch()
    cache, xml = build_outputs(sessions, locations, tracks)
    client = boto3.client("s3")
    client.put_object(
        Body=json.dumps(cache).encode("utf-8"),
        Bucket=config.cache_bucket,
        Key=config.cache_key,
        ContentType="application/json",
    )
    client.put_object(
        Body=xml.encode("utf-8"),
        Bucket=config.cache_bucket,
        Key=config.frab_key,
        ContentType="text/xml",
    )
    return {
        'statusCode': 200,
        'body': json.dumps({
            "sessions": len(sessions),
            "locations": len(locations),
            "tracks": len(tracks),
        })
    }


if __name__ == "__main__":
    if not config.cache_file:
        raise SystemExit("Set CACHE_FILE to write the cache to a local file")
    sessions, locations, tracks = fetch()
    cache, xml = build_outputs(sessions, locations, tracks)
    with open(config.cache_file, "w") as filehandle:
        json.dump(cache, filehandle)
    print(f"Wrote {config.cache_file} ({len(sessions)} sessions)")
