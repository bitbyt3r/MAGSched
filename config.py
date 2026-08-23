import os

time_loop = os.environ.get("TIME_LOOP", "false").lower() == "true"

cache_bucket = os.environ.get("CACHE_BUCKET", "magsched-cache")
cache_key = os.environ.get("CACHE_KEY", "cache.json")
# When set, read/write the cache from this local file instead of S3 (local dev and tests).
cache_file = os.environ.get("CACHE_FILE", "")

guidebook_api_key = os.environ.get("GUIDEBOOK_API_KEY", "")
guidebook_guide = os.environ.get("GUIDEBOOK_GUIDE", "")

acronym = os.environ.get("ACRONYM", "super2026")
title = os.environ.get("TITLE", "Super MAGFest 2026")
start = os.environ.get("START", "2026-01-22")
end = os.environ.get("END", "2026-01-25")
days = os.environ.get("DAYS", "4")
timeslot_duration = os.environ.get("TIMESLOT_DURATION", "00:15")
time_zone_name = os.environ.get("TIME_ZONE_NAME", "America/New_York")
base_url = os.environ.get("BASE_URL", "https://schedule.magfest.net")
