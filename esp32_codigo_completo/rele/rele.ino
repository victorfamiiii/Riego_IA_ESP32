#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <time.h>

// WiFi
const char* ssid = "";
const char* password = "";

// MQTT broker (server)
// Prueba de conexión: usa el hostname del certificado del broker.
const char* mqttHost = "";
const int mqttPort = 8883;
const bool MQTT_TEST_INSECURE = true;  // false: comprueba CA
// Credenciales MQTT — deben coincidir con MQTT_ESP32_USER / MQTT_ESP32_PASSWORD en .env del servidor
const char* mqttUser = "";
const char* mqttPass = "";  // <- mismo valor que MQTT_ESP32_PASSWORD en .env
const char MQTT_CA_CERT[] PROGMEM = R"EOF(

)EOF";

// Intervals
const unsigned long SENSOR_UPLOAD_INTERVAL_MS = 300000;
const unsigned long COMMAND_POLL_INTERVAL_MS = 300000;
const unsigned long ACTIVE_COMMAND_POLL_INTERVAL_MS = 5000;
const unsigned long MQTT_HANDSHAKE_TIMEOUT_SEC = 30;
const unsigned long MQTT_SOCKET_TIMEOUT_SEC = 30;
const unsigned long MQTT_KEEPALIVE_SEC = 60;
const unsigned long NTP_SYNC_TIMEOUT_MS = 15000;
const unsigned long MQTT_RETRY_DELAY_MS = 2000;
const unsigned long MQTT_RESTART_DELAY_MS = 5000;
const int WIFI_MAX_ATTEMPTS = 40;
const int MQTT_MAX_ATTEMPTS = 10;

bool syncSystemTime() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov", "time.google.com");
  unsigned long start = millis();
  struct tm timeinfo;
  while (millis() - start < NTP_SYNC_TIMEOUT_MS) {
    if (getLocalTime(&timeinfo)) {
      Serial.printf("NTP synced: %04d-%02d-%02d %02d:%02d:%02d\n",
                    timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
                    timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
      return true;
    }
    delay(500);
  }

  Serial.println("NTP sync failed, TLS certificate validation may fail");
  return false;
}

// Plant mapping
const char* PLANT_TYPE_1 = "lechuga";
const char* PLANT_TYPE_2 = "fresa";

// VEML7700
#define VEML7700_ADDR  0x10
#define REG_ALS_CONF   0x00
#define REG_ALS_DATA   0x04

// Soil sensors
#define SOIL1_PIN 39  // VN (SENSOR_VN) en ESP32
#define SOIL2_PIN 36
#define SOIL1_SECO   90
#define SOIL1_HUMEDO 3000
#define SOIL2_SECO   3060
#define SOIL2_HUMEDO 1500

// Relays (active LOW)
#define RELE1_PIN 27
#define RELE2_PIN 13

bool rele1On = false;
bool rele2On = false;
int relayEventId[2] = {0, 0};
unsigned long relayStopAt[2] = {0, 0};
String relayReason[2] = {"", ""};

String macAddress;
String topicTelemetrySoil;
String topicTelemetryLuminosity;
String topicCommandsRequest;
String topicCommandsResponse;
String topicNotifications;

WiFiClientSecure wifiClient;
PubSubClient mqttClient(wifiClient);

float readSoilRaw(int sensor) {
  if (sensor == 1) {
    return analogRead(SOIL1_PIN);
  }
  return analogRead(SOIL2_PIN);
}

uint16_t readALS() {
  Wire.beginTransmission(VEML7700_ADDR);
  Wire.write(REG_ALS_DATA);
  Wire.endTransmission(false);
  Wire.requestFrom(VEML7700_ADDR, 2);
  if (Wire.available() < 2) return 0;
  uint16_t low = Wire.read();
  uint16_t high = Wire.read();
  return (high << 8) | low;
}

const char* getPlantTypeForRelay(int relay) {
  return relay == 1 ? PLANT_TYPE_1 : PLANT_TYPE_2;
}

bool isRelayActive(int relay) {
  return relay == 1 ? rele1On : rele2On;
}

void setRelayState(int relay, bool active) {
  if (relay == 1) {
    rele1On = active;
    digitalWrite(RELE1_PIN, active ? LOW : HIGH);
  } else if (relay == 2) {
    rele2On = active;
    digitalWrite(RELE2_PIN, active ? LOW : HIGH);
  }
}

void sendNotification(const char* notificationType, int relay, const String& reason, float humedad) {
  StaticJsonDocument<512> doc;
  doc["mac_address"] = macAddress;
  doc["esp32_ip"] = WiFi.localIP().toString();
  doc["event_id"] = relayEventId[relay - 1];
  doc["relay"] = relay;
  doc["plant_type"] = getPlantTypeForRelay(relay);
  doc["notification_type"] = notificationType;
  doc["reason"] = reason;
  doc["humedad_suelo"] = humedad;

  JsonObject payload = doc.createNestedObject("payload");
  payload["relay_active"] = isRelayActive(relay);
  payload["relay_reason"] = relayReason[relay - 1];

  char buffer[512];
  size_t n = serializeJson(doc, buffer, sizeof(buffer));
  mqttClient.publish(topicNotifications.c_str(), buffer, n);
}

void sendSensorReadNotification(int relay, const String& requestId, float humedadRaw) {
  StaticJsonDocument<512> doc;
  doc["mac_address"] = macAddress;
  doc["esp32_ip"] = WiFi.localIP().toString();
  doc["event_id"] = relayEventId[relay - 1];
  doc["relay"] = relay;
  doc["plant_type"] = getPlantTypeForRelay(relay);
  doc["notification_type"] = "poll";
  doc["reason"] = "sensor_read";
  doc["humedad_suelo"] = humedadRaw;

  JsonObject payload = doc.createNestedObject("payload");
  payload["kind"] = "sensor_read";
  payload["request_id"] = requestId;
  payload["value_raw"] = humedadRaw;
  payload["relay_active"] = isRelayActive(relay);
  payload["relay_reason"] = relayReason[relay - 1];

  char buffer[512];
  size_t n = serializeJson(doc, buffer, sizeof(buffer));
  mqttClient.publish(topicNotifications.c_str(), buffer, n);
}

void startIrrigation(int relay, int durationSeconds, int eventId, const String& reason) {
  setRelayState(relay, true);
  relayEventId[relay - 1] = eventId;
  relayReason[relay - 1] = reason;
  relayStopAt[relay - 1] = millis() + ((unsigned long)durationSeconds * 1000UL);

  Serial.printf("Relay %d ON for %d s | event %d | reason: %s\n", relay, durationSeconds, eventId, reason.c_str());
  sendNotification("start", relay, reason, relay == 1 ? readSoilRaw(1) : readSoilRaw(2));
}

void stopIrrigation(int relay, const char* notificationType, const String& reason, float humedad) {
  if (!isRelayActive(relay) && relayEventId[relay - 1] == 0) return;

  setRelayState(relay, false);
  relayStopAt[relay - 1] = 0;

  Serial.printf("Relay %d OFF | event %d | reason: %s\n", relay, relayEventId[relay - 1], reason.c_str());
  sendNotification(notificationType, relay, reason, humedad);
  relayEventId[relay - 1] = 0;
  relayReason[relay - 1] = "";
}

void publishSoilAndLuminosity(float soil1Raw, float soil2Raw, float lux) {
  // UN SOLO mensaje con ambas plantas para evitar duplicados
  StaticJsonDocument<512> soilDoc;
  soilDoc["mac_address"] = macAddress;
  soilDoc["esp32_ip"] = WiFi.localIP().toString();
  
  JsonArray zones = soilDoc.createNestedArray("zones");
  
  JsonObject zone1 = zones.createNestedObject();
  zone1["relay"] = 1;
  zone1["tipo_planta"] = PLANT_TYPE_1;
  zone1["humedad_suelo"] = soil1Raw;
  
  JsonObject zone2 = zones.createNestedObject();
  zone2["relay"] = 2;
  zone2["tipo_planta"] = PLANT_TYPE_2;
  zone2["humedad_suelo"] = soil2Raw;
  
  char payloadSoil[512];
  size_t nSoil = serializeJson(soilDoc, payloadSoil, sizeof(payloadSoil));
  mqttClient.publish(topicTelemetrySoil.c_str(), payloadSoil, nSoil);

  // Luminosidad en mensaje separado (como antes)
  StaticJsonDocument<256> lum;
  lum["mac_address"] = macAddress;
  lum["esp32_ip"] = WiFi.localIP().toString();
  lum["luminosidad"] = lux;
  char payloadLum[256];
  size_t nLum = serializeJson(lum, payloadLum, sizeof(payloadLum));
  mqttClient.publish(topicTelemetryLuminosity.c_str(), payloadLum, nLum);
}

void publishCommandRequest() {
  StaticJsonDocument<512> doc;
  doc["mac_address"] = macAddress;
  doc["esp32_ip"] = WiFi.localIP().toString();

  JsonArray zones = doc.createNestedArray("zones");

  JsonObject zone1 = zones.createNestedObject();
  zone1["relay"] = 1;
  zone1["plant_type"] = PLANT_TYPE_1;
  zone1["active"] = rele1On;
  zone1["event_id"] = relayEventId[0];

  JsonObject zone2 = zones.createNestedObject();
  zone2["relay"] = 2;
  zone2["plant_type"] = PLANT_TYPE_2;
  zone2["active"] = rele2On;
  zone2["event_id"] = relayEventId[1];

  char buffer[512];
  size_t n = serializeJson(doc, buffer, sizeof(buffer));
  mqttClient.publish(topicCommandsRequest.c_str(), buffer, n);
}

void handleCommandsResponse(const JsonDocument& responseDoc) {
  JsonArrayConst commands = responseDoc["commands"].as<JsonArrayConst>();
  for (JsonObjectConst cmd : commands) {
    int relay = cmd["relay"] | 0;
    const char* command = cmd["command"] | "OFF";
    int duration = cmd["duration"] | 0;
    int eventId = cmd["event_id"] | 0;
    String requestId = String((const char*)(cmd["request_id"] | ""));
    String reason = String((const char*)(cmd["reason"] | "Sin razon"));

    if (relay < 1 || relay > 2) continue;

    if (strcmp(command, "READ_SOIL") == 0) {
      float humedad = relay == 1 ? readSoilRaw(1) : readSoilRaw(2);
      sendSensorReadNotification(relay, requestId, humedad);
      continue;
    }

    if (strcmp(command, "ON") == 0) {
      int idx = relay - 1;
      bool sameActiveEvent = isRelayActive(relay) && eventId == relayEventId[idx] && eventId != 0;

      // Evita recortar la duración por refrescos ON del mismo evento.
      // El tiempo de riego se fija cuando el evento arranca por primera vez.
      if (!sameActiveEvent) {
        startIrrigation(relay, duration, eventId, reason);
      }
    } else {
      float humedad = relay == 1 ? readSoilRaw(1) : readSoilRaw(2);
      stopIrrigation(relay, "stop", reason, humedad);
    }
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String t = String(topic);
  String body;
  for (unsigned int i = 0; i < length; i++) body += (char)payload[i];

  if (t == topicCommandsResponse) {
    DynamicJsonDocument doc(2048);
    if (deserializeJson(doc, body) == DeserializationError::Ok) {
      handleCommandsResponse(doc);
    } else {
      Serial.println("Error parsing MQTT commands response");
    }
  }
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < WIFI_MAX_ATTEMPTS) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("WiFi OK | IP: ");
    Serial.println(WiFi.localIP());
    return;
  }

  Serial.println();
  Serial.println("WiFi failed, restarting ESP32 in 5s...");
  delay(5000);
  ESP.restart();
}

void connectMqtt() {
  Serial.printf("Connecting MQTT to %s:%d\n", mqttHost, mqttPort);
  unsigned long attempt = 0;
  while (!mqttClient.connected() && attempt < MQTT_MAX_ATTEMPTS) {
    attempt++;
    String clientId = "esp32-soil-" + macAddress;
    bool ok;
    Serial.printf("MQTT connect attempt %lu as %s\n", attempt, clientId.c_str());
    if (strlen(mqttUser) > 0) {
      ok = mqttClient.connect(clientId.c_str(), mqttUser, mqttPass);
    } else {
      ok = mqttClient.connect(clientId.c_str());
    }

    if (ok) {
      mqttClient.subscribe(topicCommandsResponse.c_str());
      Serial.println("MQTT connected and subscribed");
    } else {
      Serial.printf("MQTT connect failed rc=%d (attempt %lu)\n", mqttClient.state(), attempt);
      delay(MQTT_RETRY_DELAY_MS);
    }
  }

  if (mqttClient.connected()) {
    return;
  }

  Serial.println("MQTT failed after max attempts, restarting ESP32 in 5s...");
  delay(MQTT_RESTART_DELAY_MS);
  ESP.restart();
}

void checkRelayTimeouts(float soil1Raw, float soil2Raw) {
  unsigned long now = millis();

  for (int relay = 1; relay <= 2; relay++) {
    if (!isRelayActive(relay)) continue;
    if (relayStopAt[relay - 1] > 0 && now >= relayStopAt[relay - 1]) {
      float humedad = relay == 1 ? soil1Raw : soil2Raw;
      stopIrrigation(relay, "completed", "Duracion completada", humedad);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  analogReadResolution(12);
  analogSetPinAttenuation(SOIL1_PIN, ADC_11db);
  analogSetPinAttenuation(SOIL2_PIN, ADC_11db);

  pinMode(RELE1_PIN, OUTPUT);
  pinMode(RELE2_PIN, OUTPUT);
  digitalWrite(RELE1_PIN, HIGH);
  digitalWrite(RELE2_PIN, HIGH);

  Wire.begin(22, 21);
  delay(500);
  Wire.beginTransmission(VEML7700_ADDR);
  Wire.write(REG_ALS_CONF);
  Wire.write(0x00);
  Wire.write(0x00);
  Wire.endTransmission();
  delay(150);

  connectWiFi();
  macAddress = WiFi.macAddress();

  syncSystemTime();

      // DEBUG: imprimir los primeros 80 chars de la CA que está en memoria
    Serial.println("CA cert en uso:");
    Serial.println(String(MQTT_CA_CERT).substring(0, 80));

  if (MQTT_TEST_INSECURE) {
    wifiClient.setInsecure();
    Serial.println("MQTT TLS test mode: setInsecure enabled");
  } else {
    wifiClient.setCACert(MQTT_CA_CERT);
    wifiClient.setHandshakeTimeout(MQTT_HANDSHAKE_TIMEOUT_SEC * 1000);  // Convert to milliseconds
  }

  topicTelemetrySoil = "esp32/" + macAddress + "/telemetry/soil";
  topicTelemetryLuminosity = "esp32/" + macAddress + "/telemetry/luminosity";
  topicCommandsRequest = "esp32/" + macAddress + "/commands/request";
  topicCommandsResponse = "esp32/" + macAddress + "/commands/response";
  topicNotifications = "esp32/" + macAddress + "/notifications";

  mqttClient.setServer(mqttHost, mqttPort);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(4096);
  mqttClient.setKeepAlive(MQTT_KEEPALIVE_SEC);
  mqttClient.setSocketTimeout(MQTT_SOCKET_TIMEOUT_SEC);

  Serial.println("MQTT topics ready");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (!mqttClient.connected()) {
    connectMqtt();
  }

  mqttClient.loop();

  float soil1Raw = readSoilRaw(1);
  float soil2Raw = readSoilRaw(2);
  float lux = readALS() * 0.0576;

  checkRelayTimeouts(soil1Raw, soil2Raw);

  static unsigned long lastSend = 0;
  if (millis() - lastSend > SENSOR_UPLOAD_INTERVAL_MS || lastSend == 0) {
    publishSoilAndLuminosity(soil1Raw, soil2Raw, lux);
    Serial.printf("Soil1Raw=%.0f Soil2Raw=%.0f Lux=%.0f\n", soil1Raw, soil2Raw, lux);
    lastSend = millis();
  }

  static unsigned long lastCommandPoll = 0;
  unsigned long commandInterval = (rele1On || rele2On) ? ACTIVE_COMMAND_POLL_INTERVAL_MS : COMMAND_POLL_INTERVAL_MS;
  if (millis() - lastCommandPoll > commandInterval || lastCommandPoll == 0) {
    publishCommandRequest();
    lastCommandPoll = millis();
  }

  delay(50);
}
