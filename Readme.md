# MAGSched

Schedule caching server supporting multiple upstreams.

The main goal is to avoid having any API usage limits that external providers impose by self hosting a local copy of the schedule. Additionally, it provides a very simple interface for downstream consumers.

## Configuration

The following environment variables are used to configure the backend:

* REDIS_HOST - The IP/hostname of the redis instance
* REDIS_PORT - The port to use for redis
* REDIS_DB - The DB number to use for redis (generally a number from 0-15)
* REFRESH_DELAY - How long to wait between backend polls
* BACKENDS - A json string specifying which backend services to pull from in ascending order of priority

BACKENDS takes a list of objects in this format:
```json
[
    {
        "name": "Test Guidebook",
        "type": "guidebook",
        "apikey": "aaaabbbbccccddddeeeeffff.aaaabbbbccccddddeeeeffff",
        "guide": "183391"
    },
    {
        "name": "Google Sheet",
        "type": "sheets",
        "sheet": "1dTp07uGTokckyXtNUGLRnK634twzaaKUF0Rp8XQGl20",
        "key": "aaaabbbbccccddddeeeeffff",
        "credentials": ""
    }
]
```

Currently, `sheets` and `guidebook` types are supported. Data pulled from services later in the list of backends will override data from earlier ones if they contain the same IDs. In this example, you could use Google Sheets to add or edit schedule entries from Guidebook.

### Guidebook Configuration

Guidebook requires an API key and a guide number, both as strings. Guidebook does not have permissions controls on API keys, so be very careful with them.

### Google Sheets Configuration

Google sheets requires a sheet ID which can be pulled from the URL of a sheet.

Additionally it requires a Google developer API key. See https://developers.google.com/sheets/api/quickstart/python for docs on setting up a key for this.

Finally, sheets requires credentials that have been authorized to access the user's account. If you start the server locally with credentials set to an empty string it will launch a browser window interactively to allow you to authorize it to access sheets on your account. Once that is complete, it will save the session key to the database and continually refresh it. It will also print out the value needed for this variable so that you can copy it to a remote server. If this server gets any serious use I'll probably implement the flow server side, but it should be at most a once per year thing.

## Panel Displays

To access the panel displays go <a href="/display">here</a> then select the appropriate location.

## Up Next Displays

To access the up next displays go <a href="/upnext">here</a> then select the appropriate location.

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
| schedule_tracks  |            | Filter results by whether they include a track in their list    |

`time_range_start` and `time_range_end` allow you to request results from a range of time. You can specify the endpoints in a few ways.

Each end of the range can be:
* A unix epoch timestamp
* The literal word "now"
* A relative number of seconds to now with a +/- sign in front

To get the next hour of events use `time_range_start=now&time_range_end=+3600` for example. To get events starting one hour ago until the end of the schedule use `time_range_start=-3600`.

### GET /bops-graphics

Returns a list of sessions that are schedule, but in a broadcast-friendly format.

Accepts all the same arguments as `/sessions` above.

Returns a simplified object:
```json
[
  {
    "end_time": "11:59 PM",
    "id": "29587736",
    "location": "Accessibility Services (Expo Hall E Reg Desk)",
    "name": "Accessibility Desk open",
    "start_time": "10:00 AM"
  },
  {
    "end_time": "11:00 AM",
    "id": "29587743",
    "location": "Zombie Tag (Magnolia 3)",
    "name": "Zombie Tag Sign up, Events, and Makeup",
    "start_time": "10:00 AM"
  },
  {
    "end_time": "10:00 PM",
    "id": "29587969",
    "location": "MAG Attendee Services/Info Desk (Potomac Coat Check)",
    "name": "Info Desk Open",
    "start_time": "10:00 AM"
  },
  {
    "end_time": "11:00 AM",
    "id": "29587741",
    "location": "Tabletop Panels/Discussions (Riverview Ballroom 1)",
    "name": "Donut Steel: the Original Character Panel",
    "start_time": "10:00 AM"
  },
  {
    "end_time": "12:00 PM",
    "id": "29769137",
    "location": "magFAST (Chesapeake 4,5,6)",
    "name": "magFAST Preshow and Swadge Showcase",
    "start_time": "11:00 AM"
  }
]
```

### GET /sessions/<id>

Returns a single session object by ID:
```json
{
  "all_day": false, 
  "description": "<p> Come hang out as we start the show! Maybe donate some money to Child's Play while you're here. </p>", 
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

Returns a list of locations, uses same sorting and filtering as sessions.

### GET /locations/<id>

Returns a single location by ID:
```json
{
    "id": "3985248", 
    "name": "Annapolis 2-4 (Panels 4)"
}
```

### GET /tracks

Returns a list of tracks, uses same sorting and filtering as sessions.

### GET /tracks/<id>

Returns a single track by ID:
```json
{
    "id": "530633", 
    "name": "Arcade"
}
```

### GET /frab

Returns the complete schedule in XML/Frab format