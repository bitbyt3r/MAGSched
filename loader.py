import json

import config
from guidebook import Guidebook


def build_cache():
    source = Guidebook(config.guidebook_api_key, config.guidebook_guide)
    return {
        "sessions": [x.serialize() for x in source.list_sessions()],
        "locations": [x.serialize() for x in source.list_locations()],
        "tracks": [x.serialize() for x in source.list_tracks()],
    }


def lambda_handler(event, context):
    import boto3
    resources = build_cache()
    boto3.client("s3").put_object(
        Body=json.dumps(resources).encode("utf-8"),
        Bucket=config.cache_bucket,
        Key=config.cache_key,
        ContentType="application/json",
    )
    return {
        'statusCode': 200,
        'body': json.dumps({name: len(items) for name, items in resources.items()})
    }


if __name__ == "__main__":
    if not config.cache_file:
        raise SystemExit("Set CACHE_FILE to write the cache to a local file")
    with open(config.cache_file, "w") as filehandle:
        json.dump(build_cache(), filehandle)
    print(f"Wrote {config.cache_file}")
