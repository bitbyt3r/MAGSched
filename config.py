import os
import json

backends = json.loads(os.environ.get("BACKENDS", '[]'))
redis_host = os.environ.get("REDIS_HOST", "localhost")
redis_port = int(os.environ.get("REDIS_PORT", "6379"))
redis_db = int(os.environ.get("REDIS_DB", "0"))
refresh_delay = float(os.environ.get("REFRESH_DELAY", "60"))
time_loop = bool(os.environ.get("TIME_LOOP", "true").lower() == "true")
time_zone = os.environ.get("TIME_ZONE", "America/New_York")

acronym = os.environ.get("ACRONYM", "super2024")
title = os.environ.get("TITLE", "Super MAGFest 2024")
start = os.environ.get("START", "2024-01-18")
end = os.environ.get("END", "2024-01-21")
days = os.environ.get("DAYS", "4")
timeslot_duration = os.environ.get("TIMESLOT_DURATION", "00:15")
time_zone_name = os.environ.get("TIME_ZONE_NAME", "America/New_York")
base_url = os.environ.get("BASE_URL", "https://magsched.hackafe.net")