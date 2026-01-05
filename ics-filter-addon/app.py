import json
import re
import time
import requests
from flask import Flask, Response, abort, request
from icalendar import Calendar

OPTIONS_FILE = "/data/options.json"

def load_options():
    with open(OPTIONS_FILE, "r") as f:
        return json.load(f)

options = load_options()

ICS_URL = options["ics_url"]
USER_AGENT = options.get("user_agent", "HomeAssistant-ICS-Filter/1.1")
CACHE_MINUTES = options.get("cache_minutes", 10)
FILTERS = options.get("filters", [])

cache = {
    "timestamp": 0,
    "data": None
}

app = Flask(__name__)

def event_allowed(event):
    for rule in FILTERS:
        field = rule.get("field")
        value = str(event.get(field, ""))

        if "contains" in rule:
            if rule["contains"].lower() in value.lower():
                return False

        if "regex" in rule:
            if re.search(rule["regex"], value, re.IGNORECASE):
                return False

    return True

@app.route("/calendar.ics")
def calendar():
    now = time.time()

    # Serve cached calendar if valid
    if cache["data"] and now - cache["timestamp"] < CACHE_MINUTES * 60:
        return Response(cache["data"], mimetype="text/calendar")

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/calendar"
    }

    try:
        response = requests.get(
            ICS_URL,
            headers=headers,
            timeout=15
        )
        response.raise_for_status()
    except Exception as e:
        print(f"ERROR: Failed to fetch ICS feed: {e}")
        abort(502)

    original_cal = Calendar.from_ical(response.text)

    new_cal = Calendar()
    for key, value in original_cal.items():
        new_cal.add(key, value)

    for event in original_cal.walk("VEVENT"):
        if event_allowed(event):
            new_cal.add_component(event)

    data = new_cal.to_ical()
    cache["timestamp"] = now
    cache["data"] = data

    print("ICS calendar fetched and filtered successfully")

    return Response(data, mimetype="text/calendar")

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8085)
