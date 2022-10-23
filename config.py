import os
import json

backends = json.loads(os.environ.get("BACKENDS", '[{"name": "MAGFest 2022 Guidebook", "type": "guidebook", "apikey": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOjgzOTMxODMsImF1ZCI6Im9wZW5fYXBpIiwiYXBpX2tleSI6MTU2Nn0.nZOCec1DFr-RDXYDBGrpAHreoJf3hTGUmKsrOtdSbVA","guide": "183391"}]'))
redis_host = os.environ.get("REDIS_HOST", "localhost")
redis_port = int(os.environ.get("REDIS_PORT", "6379"))
redis_db = int(os.environ.get("REDIS_DB", "0"))
refresh_delay = float(os.environ.get("REFRESH_DELAY", "60"))
