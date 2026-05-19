# 💡 Bulb Identifier — Home Assistant Add-on

Identify and rename your Zigbee light bulbs without guessing which is which.

The add-on connects to Zigbee2MQTT via MQTT, cycles through each light bulb one
at a time by toggling it on and off — so you can walk around and confirm which
physical bulb is flashing. When you find the right one, click **"That's it!"**,
type a new name, and the rename is pushed directly to Zigbee2MQTT (which
propagates it to Home Assistant automatically).

## Features

- Auto-cycles through all discovered Z2M light devices
- Saves the bulb's previous state (on/off + brightness + colour temp) and restores it after flashing
- Rename directly from the UI — no YAML or MQTT client needed
- Also lets you flash individual bulbs manually from the list
- Runs as an HA Ingress add-on (available in the sidebar)

## Installation

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**
2. Click the three-dot menu (⋮) → **Repositories**
3. Add `https://github.com/andershagenhansen/ha-addons`
4. Find **Bulb Identifier** and install it

## Configuration

| Option           | Default          | Description                          |
|------------------|------------------|--------------------------------------|
| `mqtt_host`      | `core-mosquitto` | MQTT broker hostname                 |
| `mqtt_port`      | `1883`           | MQTT broker port                     |
| `mqtt_user`      | `mqtt-user`      | MQTT username                        |
| `mqtt_password`  | `Velkommen1!`    | MQTT password                        |
| `flash_duration` | `3`              | Seconds bulb stays ON per flash      |
| `flash_cycles`   | `2`              | Number of on/off cycles per bulb     |

## Usage

1. Open the add-on via the sidebar (**Bulb Identifier**)
2. Click **▶ Start Auto-Cycle**
3. Stand by the bulb you want to identify — when it flashes, click **✓ That's it!**
4. Type the new name and press **Save**
5. Repeat for remaining bulbs, or click **Skip →** to move on

You can also click **⚡ Flash** on any individual card to identify it manually,
and **✎ Rename** to rename it without cycling.
