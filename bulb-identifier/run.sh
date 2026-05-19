#!/usr/bin/with-contenv bashio

export MQTT_HOST=$(bashio::config 'mqtt_host')
export MQTT_PORT=$(bashio::config 'mqtt_port')
export MQTT_USER=$(bashio::config 'mqtt_user')
export MQTT_PASSWORD=$(bashio::config 'mqtt_password')
export FLASH_DURATION=$(bashio::config 'flash_duration')
export FLASH_CYCLES=$(bashio::config 'flash_cycles')
export INGRESS_PATH=$(bashio::addon.ingress_entry)

bashio::log.info "Starting Bulb Identifier..."
bashio::log.info "MQTT: ${MQTT_HOST}:${MQTT_PORT}"

python3 /app/main.py
