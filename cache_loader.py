import traceback
import time

import database
import backends
import config

def refresh_cache(sources):
    all_sessions = {}
    all_locations = {}
    all_tracks = {}
    for source in sources:
        sessions = source.list_sessions()
        locations = source.list_locations()
        tracks = source.list_tracks()
        
        for session in sessions:
            all_sessions[session.id] = session

        for location in locations:
            all_locations[location.id] = location

        for track in tracks:
            all_tracks[track.id] = track

    database.Session.full_update(all_sessions.values())
    database.Location.full_update(all_locations.values())
    database.Track.full_update(all_tracks.values())

if __name__ == "__main__":
    sources = backends.get_backends(config.backends)
    while True:
        try:
            refresh_cache(sources)
            print("Cache reloaded successfully")
        except:
            print("Cache reloading failed")
            traceback.print_exc()
        time.sleep(config.refresh_delay)