import json
import re
import time
import requests
from flask import Flask, Response, abort
from icalendar import Calendar
from datetime import datetime

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
    "calendar": None,
    "raw": None
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

def fetch_calendar():
    now = time.time()

    if cache["calendar"] and now - cache["timestamp"] < CACHE_MINUTES * 60:
        return cache["calendar"], cache["raw"]

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/calendar"
    }

    try:
        response = requests.get(ICS_URL, headers=headers, timeout=15)
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

    raw = new_cal.to_ical()
    cache.update({
        "timestamp": now,
        "calendar": new_cal,
        "raw": raw
    })

    return new_cal, raw

def format_dt(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)

@app.route("/")
def index():
    cal, _ = fetch_calendar()

    rows = []
    for event in cal.walk("VEVENT"):
        summary = event.get("summary", "—")
        start = format_dt(event.decoded("dtstart"))
        end = format_dt(event.decoded("dtend")) if event.get("dtend") else "—"
        description = event.get("description", "")

        rows.append(f"""
        <tr>
            <td>{summary}</td>
            <td>{start}</td>
            <td>{end}</td>
            <td>{description}</td>
        </tr>
        """)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Filtered Calendar</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                padding: 20px;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
            }}
            th, td {{
                border: 1px solid #ccc;
                padding: 8px;
                vertical-align: top;
            }}
            th {{
                background: #f0f0f0;
            }}
        </style>
    </head>
    <body>
        <h1>Filtered Calendar</h1>
        <p>Events shown are the same as served via <code>/calendar.ics</code></p>

        <table>
            <tr>
                <th>Summary</th>
                <th>Start</th>
                <th>End</th>
                <th>Description</th>
            </tr>
            {''.join(rows)}
        </table>
    </body>
    </html>
    """

    return html

@app.route("/calendar.ics")
def calendar():
    _, raw = fetch_calendar()
    return Response(raw, mimetype="text/calendar")

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8085)
