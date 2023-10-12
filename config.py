import os
import json

backends = json.loads(os.environ.get("BACKENDS", '[]'))
redis_host = os.environ.get("REDIS_HOST", "localhost")
redis_port = int(os.environ.get("REDIS_PORT", "6379"))
redis_db = int(os.environ.get("REDIS_DB", "0"))
refresh_delay = float(os.environ.get("REFRESH_DELAY", "60"))
time_loop = bool(os.environ.get("TIME_LOOP", "true").lower() == "true")
time_zone = os.environ.get("TIME_ZONE", "America/New_York")