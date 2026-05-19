import os
import json
import time
import threading
import logging
from flask import Flask, render_template, jsonify, request
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)

MQTT_HOST      = os.environ.get("MQTT_HOST", "core-mosquitto")
MQTT_PORT      = int(os.environ.get("MQTT_PORT", 1883))
MQTT_USER      = os.environ.get("MQTT_USER", "")
MQTT_PASSWORD  = os.environ.get("MQTT_PASSWORD", "")
FLASH_DURATION = int(os.environ.get("FLASH_DURATION", 3))
FLASH_CYCLES   = int(os.environ.get("FLASH_CYCLES", 2))
INGRESS_PATH   = os.environ.get("INGRESS_PATH", "")

# -- State ---------------------------------------------------------------------
devices        = {}          # ieee -> device info
device_states  = {}          # friendly_name -> last known state payload
active_flash   = None        # friendly_name currently being flashed
flash_lock     = threading.Lock()
devices_ready  = threading.Event()

# -- MQTT callbacks ------------------------------------------------------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info("MQTT connected")
        client.subscribe("zigbee2mqtt/bridge/devices")
        client.subscribe("zigbee2mqtt/+")
    else:
        log.error(f"MQTT connect failed rc={rc}")

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
    except Exception:
        return

    if topic == "zigbee2mqtt/bridge/devices":
        _handle_devices(payload)
        return

    parts = topic.split("/")
    if len(parts) == 2:
        fname = parts[1]
        if isinstance(payload, dict):
            device_states[fname] = payload

def _is_light(exposes):
    """Return True only if the device has a top-level type=='light' expose.
    Smart plugs have type=='switch', sensors have type=='numeric'/'binary', etc.
    """
    for item in exposes:
        if item.get("type") == "light":
            return True
    return False

def _get_features(exposes):
    features = set()
    def walk(items):
        for item in items:
            if item.get("name") in ("state", "brightness", "color_temp", "color_xy"):
                features.add(item["name"])
            if "features" in item:
                walk(item["features"])
    walk(exposes)
    return list(features)

def _handle_devices(payload):
    global devices
    tmp = {}
    for dev in payload:
        if dev.get("type") not in ("Router", "EndDevice"):
            continue
        exposes = dev.get("definition", {}).get("exposes", [])
        if not _is_light(exposes):
            log.info(f"Skipping non-light: {dev.get('friendly_name')} ({dev.get('definition', {}).get('model', '?')})")
            continue
        ieee  = dev["ieee_address"]
        fname = dev.get("friendly_name", ieee)
        tmp[ieee] = {
            "ieee":          ieee,
            "friendly_name": fname,
            "model":         dev.get("definition", {}).get("model", ""),
            "vendor":        dev.get("definition", {}).get("vendor", ""),
            "description":   dev.get("definition", {}).get("description", ""),
            "features":      _get_features(exposes),
        }
        mqttc.subscribe(f"zigbee2mqtt/{fname}")
    devices = tmp
    devices_ready.set()
    log.info(f"Discovered {len(devices)} light device(s)")

# -- MQTT client ---------------------------------------------------------------
mqttc = mqtt.Client()
mqttc.on_connect = on_connect
mqttc.on_message = on_message
if MQTT_USER:
    mqttc.username_pw_set(MQTT_USER, MQTT_PASSWORD)
mqttc.connect_async(MQTT_HOST, MQTT_PORT, 60)
mqttc.loop_start()

# -- Flash logic ---------------------------------------------------------------
def _get_state(fname):
    return dict(device_states.get(fname, {}))

def _set_state(fname, state_payload):
    mqttc.publish(f"zigbee2mqtt/{fname}/set", json.dumps(state_payload))

def flash_device(fname):
    with flash_lock:
        global active_flash
        active_flash = fname

        mqttc.publish(f"zigbee2mqtt/{fname}/get", json.dumps({"state": ""}))
        time.sleep(0.4)
        saved  = _get_state(fname)
        was_on = saved.get("state", "OFF") == "ON"

        for _ in range(FLASH_CYCLES):
            _set_state(fname, {"state": "ON", "brightness": 254})
            time.sleep(FLASH_DURATION)
            _set_state(fname, {"state": "OFF"})
            time.sleep(0.8)

        restore = {"state": "ON" if was_on else "OFF"}
        if "brightness" in saved:
            restore["brightness"] = saved["brightness"]
        if "color_temp" in saved:
            restore["color_temp"] = saved["color_temp"]
        _set_state(fname, restore)

        active_flash = None

# -- Flask routes --------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", ingress_path=INGRESS_PATH)

@app.route("/api/devices")
def api_devices():
    devices_ready.wait(timeout=10)
    return jsonify(list(devices.values()))

@app.route("/api/flash", methods=["POST"])
def api_flash():
    data = request.get_json()
    fname = data.get("friendly_name")
    if not fname:
        return jsonify({"error": "missing friendly_name"}), 400
    if active_flash:
        return jsonify({"error": f"already flashing {active_flash}"}), 409
    t = threading.Thread(target=flash_device, args=(fname,), daemon=True)
    t.start()
    return jsonify({"ok": True, "flashing": fname})

@app.route("/api/rename", methods=["POST"])
def api_rename():
    data = request.get_json()
    old_name = data.get("from")
    new_name = data.get("to")
    if not old_name or not new_name:
        return jsonify({"error": "missing from/to"}), 400
    mqttc.publish("zigbee2mqtt/bridge/request/device/rename", json.dumps({"from": old_name, "to": new_name}))
    log.info(f"Rename requested: {old_name} -> {new_name}")
    for ieee, dev in devices.items():
        if dev["friendly_name"] == old_name:
            dev["friendly_name"] = new_name
            break
    return jsonify({"ok": True})

@app.route("/api/status")
def api_status():
    return jsonify({"active_flash": active_flash})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8765, debug=False)
