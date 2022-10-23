import backends.guidebook as guidebook
import backends.sheets as sheets

def get_backends(config):
    backends = []
    for backend in config:
        if backend.get("type") == "guidebook":
            backends.append(guidebook.Guidebook_Backend(backend))
        elif backend.get("type") == "sheets":
            backends.append(sheets.Sheets_Backend(backend))
            pass
    return backends