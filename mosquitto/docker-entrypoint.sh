#!/bin/sh
set -e

ESP32_USER="${MQTT_ESP32_USER:-esp32}"
ESP32_PASS="${MQTT_ESP32_PASSWORD:-}"
BRIDGE_USER="${MQTT_BRIDGE_USER:-bridge}"
BRIDGE_PASS="${MQTT_BRIDGE_PASSWORD:-}"

if [ -z "$ESP32_PASS" ] || [ -z "$BRIDGE_PASS" ]; then
    echo "[MQTT] ERROR: MQTT_ESP32_PASSWORD y MQTT_BRIDGE_PASSWORD deben estar definidos en .env"
    exit 1
fi

PASSWD_FILE="/mosquitto/data/passwd"
TLS_DIR="/mosquitto/data/tls"
TLS_CERT="${TLS_DIR}/mqtt-server.pem"
TLS_KEY="${TLS_DIR}/mqtt-server.key"

# Generar passwd file desde cero en cada arranque
rm -f "$PASSWD_FILE"
mosquitto_passwd -b -c "$PASSWD_FILE" "$ESP32_USER" "$ESP32_PASS"
mosquitto_passwd -b    "$PASSWD_FILE" "$BRIDGE_USER" "$BRIDGE_PASS"
chown mosquitto:mosquitto "$PASSWD_FILE"
chmod 640 "$PASSWD_FILE"

mkdir -p "$TLS_DIR"
cp /mosquitto/certs/mqtt-server.pem "$TLS_CERT"
cp /mosquitto/certs/mqtt-server.key "$TLS_KEY"
chown mosquitto:mosquitto "$TLS_CERT" "$TLS_KEY"
chmod 644 "$TLS_CERT"
chmod 600 "$TLS_KEY"

echo "[MQTT] Autenticación habilitada: usuarios '$ESP32_USER' y '$BRIDGE_USER'"
exec /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
