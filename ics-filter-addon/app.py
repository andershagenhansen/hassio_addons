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
        start_dt = event.decoded("dtstart")
        end_dt = event.decoded("dtend") if event.get("dtend") else None
        description = event.get("description", "")

        start_str = format_dt(start_dt)
        end_str = format_dt(end_dt) if end_dt else "—"

        # data-sort attributes ensure correct sorting
        rows.append(f"""
        <tr>
            <td data-sort="{summary}">{summary}</td>
            <td data-sort="{start_dt.timestamp() if isinstance(start_dt, datetime) else ''}">{start_str}</td>
            <td data-sort="{end_dt.timestamp() if isinstance(end_dt, datetime) else ''}">{end_str}</td>
            <td data-sort="{description}">{description}</td>
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
                cursor: pointer;
                user-select: none;
            }}
            th.sort-asc::after {{
                content: " ▲";
            }}
            th.sort-desc::after {{
                content: " ▼";
            }}
        </style>
    </head>
    <body>
        <h1>Filtered Calendar</h1>
        <p>Click column headers to sort</p>

        <table id="calendarTable">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Summary</th>
                    <th onclick="sortTable(1)">Start</th>
                    <th onclick="sortTable(2)">End</th>
                    <th onclick="sortTable(3)">Description</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>

        <script>
            let sortDir = [];

            function sortTable(col) {{
                const table = document.getElementById("calendarTable");
                const tbody = table.tBodies[0];
                const rows = Array.from(tbody.rows);

                const asc = !sortDir[col];
                sortDir = [];
                sortDir[col] = asc;

                rows.sort((a, b) => {{
                    const aVal = a.cells[col].dataset.sort || "";
                    const bVal = b.cells[col].dataset.sort || "";

                    const aNum = parseFloat(aVal);
                    const bNum = parseFloat(bVal);

                    if (!isNaN(aNum) && !isNaN(bNum)) {{
                        return asc ? aNum - bNum : bNum - aNum;
                    }}

                    return asc
                        ? aVal.localeCompare(bVal)
                        : bVal.localeCompare(aVal);
                }});

                tbody.innerHTML = "";
                rows.forEach(r => tbody.appendChild(r));

                // Update header indicators
                Array.from(table.tHead.rows[0].cells).forEach((th, i) => {{
                    th.classList.remove("sort-asc", "sort-desc");
                    if (i === col) {{
                        th.classList.add(asc ? "sort-asc" : "sort-desc");
                    }}
                }});
            }}
        </script>
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
