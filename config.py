import os

time_loop = bool(os.environ.get("TIME_LOOP", "true").lower() == "true")
time_zone = os.environ.get("TIME_ZONE", "America/New_York")

acronym = os.environ.get("ACRONYM", "super2025")
title = os.environ.get("TITLE", "Super MAGFest 2025")
start = os.environ.get("START", "2025-01-23")
end = os.environ.get("END", "2025-01-26")
days = os.environ.get("DAYS", "4")
timeslot_duration = os.environ.get("TIMESLOT_DURATION", "00:15")
time_zone_name = os.environ.get("TIME_ZONE_NAME", "America/New_York")
base_url = os.environ.get("BASE_URL", "https://schedule.magfest.net")