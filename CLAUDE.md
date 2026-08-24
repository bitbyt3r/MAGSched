# MAGSched

Minimalist schedule cache for MAGFest. A loader Lambda pulls Guidebook into `s3://magsched-cache/cache.json`; a Flask frontend Lambda (wrapped with apig-wsgi) serves JSON, Frab XML, and signage pages from that cache.

## Commands

- Tests: `pip install -r requirements-dev.txt && pytest`
- Run locally: `CACHE_FILE=tests/fixture_cache.json TIME_LOOP=true flask --app frontend run`
- Deploy: push to `main` (`.github/workflows/deploy.yaml` runs tests, then deploys both lambdas from one shared zip)

## Layout

- `frontend.py` - every HTTP route and the search/filter engine; `/frab` redirects to the pregenerated S3 object
- `loader.py` + `guidebook.py` - ingest (writes `cache.json` + `frab.xml` to S3); `frab.py` - Frab XML generation; `models.py` - Session/Location/Track; `config.py` - env vars
- `templates/signage.html` - single template behind `/display`, `/upnext`, and `/room`, parameterized by `mode`
- `tests/fixture_cache.json` - offline cache fixture with edge cases (null description, empty/unknown locations, >24h session, non-numeric id)

## Conventions

- Keep total code volume minimal; prefer stdlib over new dependencies. boto3 is provided by the Lambda runtime and intentionally not in the deploy zip.
- Guidebook/S3 names and conference metadata are env-configured in `config.py`; don't hardcode them elsewhere.
