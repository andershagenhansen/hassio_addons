import json
import requests
import re
import time
from flask import Flask, Response
from icalendar import Calendar

OPTIONS_FILE = "/data/options.json"

def load_options():
    with open(OPTIONS_FILE, "r") as f:
        return json.load(f)

options = load_options()
ICS_URL = options["ics_url"]
FILTERS = options.get("filters", [])
CACHE_MINUTES = options.get("cache_minutes", 10)

cache = {"ts": 0, "data": None}

app = Flask(__name__)

def event_allowed(event):
    for f in FILTERS:
        value = str(event.get(f["field"], ""))
        if "contains" in f and f["contains"].lower() in value.lower():
            return False
        if "regex" in f and re.search(f["regex"], value):
            return False
    return True

@app.route("/calendar.ics")
def calendar():
    now = time.time()

    if cache["data"] and now - cache["ts"] < CACHE_MINUTES * 60:
        return Response(cache["data"], mimetype="text/calendar")

    r = requests.get(ICS_URL, timeout=10)
    cal = Calendar.from_ical(r.text)

    new_cal = Calendar()
    for k, v in cal.items():
        new_cal.add(k, v)

    for event in cal.walk("VEVENT"):
        if event_allowed(event):
            new_cal.add_component(event)

    data = new_cal.to_ical()
    cache.update({"ts": now, "data": data})

    return Response(data, mimetype="text/calendar")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8085)
