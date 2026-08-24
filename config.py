import os

time_loop = os.environ.get("TIME_LOOP", "false").lower() == "true"
# Seconds added to the clock before the TIME_LOOP calculation: jump the replay
# to a different point in the schedule (e.g. -115200 shows the con as it was 32h earlier).
time_loop_offset = float(os.environ.get("TIME_LOOP_OFFSET", "0"))

cache_bucket = os.environ.get("CACHE_BUCKET", "magsched-cache")
cache_key = os.environ.get("CACHE_KEY", "cache.json")
# When set, read/write the cache from this local file instead of S3 (local dev and tests).
cache_file = os.environ.get("CACHE_FILE", "")

guidebook_api_key = os.environ.get("GUIDEBOOK_API_KEY", "")
guidebook_guide = os.environ.get("GUIDEBOOK_GUIDE", "")

acronym = os.environ.get("ACRONYM", "super2026")
title = os.environ.get("TITLE", "Super MAGFest 2026")
start = os.environ.get("START", "2026-01-08")
end = os.environ.get("END", "2026-01-11")
days = os.environ.get("DAYS", "4")
timeslot_duration = os.environ.get("TIMESLOT_DURATION", "00:15")
time_zone_name = os.environ.get("TIME_ZONE_NAME", "America/New_York")
base_url = os.environ.get("BASE_URL", "https://schedule.magfest.net")
frab_key = os.environ.get("FRAB_KEY", "frab.xml")
# When set, /frab redirects here instead of to a presigned S3 URL (e.g. a public object URL).
frab_url = os.environ.get("FRAB_URL", "")
