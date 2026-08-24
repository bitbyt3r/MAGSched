# MAGSched

Schedule caching server for MAGFest.

The main goal is to avoid any API usage limits that external providers impose by self hosting a copy of the schedule. Additionally, it provides a very simple interface for downstream consumers: digital signage, broadcast graphics, and Frab-compatible tools.

## Architecture

Two AWS Lambda functions share one deployment package, built and deployed by `.github/workflows/deploy.yaml` on pushes to `main` (tests run first, and on every pull request):

* **`magsched_guidebook_loader`** (`loader.lambda_handler`) — invoked on a schedule; pulls sessions, locations, and schedule tracks from the Guidebook Open API and writes `cache.json` plus a pregenerated `frab.xml` to S3. A failed refresh raises (visible in CloudWatch) and leaves the previous cache in place.
* **`magsched_guidebook_frontend`** (`frontend.lambda_handler`) — a Flask app served through API Gateway via `apig-wsgi`; reads `cache.json` from S3 (memoized for ~15 seconds per warm container) and serves the API and display pages below.

## Configuration

Environment variables:

* `GUIDEBOOK_API_KEY` - Guidebook Open API key (loader only). Guidebook does not have permission controls on API keys, so be very careful with them.
* `GUIDEBOOK_GUIDE` - The guide number to pull, as a string
* `CACHE_BUCKET` / `CACHE_KEY` / `FRAB_KEY` - S3 locations of the cache and the pregenerated Frab feed (defaults: `magsched-cache` / `cache.json` / `frab.xml`)
* `FRAB_URL` - When set, `/frab` redirects here (e.g. a public S3 object URL) instead of to a short-lived presigned URL
* `CACHE_FILE` - When set, read/write the cache from this local file instead of S3 (local development)
* `TIME_LOOP` - Set to `true` to replay the cached schedule endlessly, shifted onto the current time (for testing displays)
* `TIME_ZONE_NAME` - Timezone used for display and the Frab feed (default `America/New_York`)
* `ACRONYM`, `TITLE`, `START`, `END`, `DAYS`, `TIMESLOT_DURATION`, `BASE_URL` - Conference metadata included in the `/frab` feed

## Local development

```
pip install -r requirements-dev.txt
pytest
CACHE_FILE=tests/fixture_cache.json TIME_LOOP=true flask --app frontend run
```

To pull a real cache locally, set `CACHE_FILE`, `GUIDEBOOK_API_KEY`, and `GUIDEBOOK_GUIDE` and run `python loader.py`.

## Displays

* [/display](/display) - Panel displays: a broadcast overlay showing the next session in a room
* [/upnext](/upnext) - Up next displays: the next session in a room (counting one that started under 15 minutes ago)
* [/room](/room) - Room displays: the session currently running in a room, with its description
* [/tvguide](/tvguide) - A scrolling TV-guide-style schedule grid of all rooms, styled like a classic 480i cable guide channel. Add `?scanlines=off` to disable the CRT effects.

Each of `/display`, `/upnext`, and `/room` lists the locations to choose from.

## API

The REST API has the following endpoints:

### GET /sessions

Returns a list of sessions that are scheduled.

| Argument         | Default    | Description                                                     |
|------------------|------------|-----------------------------------------------------------------|
| offset           | 0          | Pagination Offset                                               |
| limit            | 10         | Pagination Result Limit (Set to -1 to get all results)          |
| sort             | start_time | Set to the name of any key to sort results by that key          |
| time_range_start |            | Allows you to filter results to a window of time. See below.    |
| time_range_end   |            | Allows you to filter results to a window of time. See below.    |
| reverse          | false      | Reverse the sort order.                                         |
| id               |            | Filter results to match an exact ID                             |
| name             |            | Filter results to match an exact name                           |
| start_time       |            | Filter results to match an exact start_time                     |
| end_time         |            | Filter results to match an exact end_time                       |
| all_day          |            | Filter results by whether they are All Day events (TRUE/FALSE)  |
| description      |            | Filter results to match an exact description                    |
| locations        |            | Filter results by whether they include a location in their list |
| tracks           |            | Filter results by whether they include a track in their list    |

`time_range_start` and `time_range_end` allow you to request results from a range of time. You can specify the endpoints in a few ways.

Each end of the range can be:
* A unix epoch timestamp
* The literal word "now"
* A relative number of seconds to now with a +/- sign in front

To get the next hour of events use `time_range_start=now&time_range_end=+3600` for example. To get events starting one hour ago until the end of the schedule use `time_range_start=-3600`.

### GET /bops-graphics

Returns a list of sessions that are scheduled, but in a broadcast-friendly format. Accepts all the same arguments as `/sessions` above.

Returns a simplified object:
```json
[
  {
    "end_time": "11:59 PM",
    "id": "29587736",
    "location": "Accessibility Services (Expo Hall E Reg Desk)",
    "name": "Accessibility Desk open",
    "start_time": "10:00 AM"
  }
]
```

### GET /sessions/&lt;id&gt;

Returns a single session object by ID:
```json
{
  "all_day": false,
  "description": "<p> Come hang out as we start the show! </p>",
  "end_time": "2022-01-06T17:00:00+00:00",
  "id": "27441254",
  "locations": [
    "3994633"
  ],
  "name": "magFAST Opening Ceremonies",
  "start_time": "2022-01-06T16:30:00+00:00",
  "tracks": [
    "530637"
  ]
}
```

### GET /locations

Returns a list of locations, uses same sorting and filtering as sessions (default sort is `name`).

### GET /locations/&lt;id&gt;

Returns a single location by ID:
```json
{
    "id": "3985248",
    "name": "Annapolis 2-4 (Panels 4)"
}
```

### GET /tracks

Returns a list of tracks, uses same sorting and filtering as locations.

### GET /tracks/&lt;id&gt;

Returns a single track by ID:
```json
{
    "id": "530633",
    "name": "Arcade"
}
```

### GET /frab

Redirects (302) to the complete schedule in XML/Frab format, pregenerated in S3 on every loader refresh. Consumers must follow redirects. (In local development with `CACHE_FILE` set, the XML is generated and returned directly.)

### GET /frab/filtered

Same format as `/frab`, but accepts all the `/sessions` arguments to filter which events are included (no result limit unless `limit` is passed).
