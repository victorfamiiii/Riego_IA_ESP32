#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <WebServer.h>
#include <DHT.h>
#include <WiFiClientSecure.h>
#include <time.h>

// WiFi
const char* ssid = "";
const char* password = "";

// MQTT (debe coincidir con docker/.env)
const char* mqttHost = "";
const int mqttPort = 8883;
const bool MQTT_TEST_INSECURE = true;
const char* mqttUser = "";
const char* mqttPass = "";
const char MQTT_CA_CERT[] PROGMEM = R"EOF(


)EOF";

// Sensores
#define DHTPIN 4
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

// IMPORTANTE: usar los mismos pines que en el sketch de prueba validado.
#define TANK_TRIG_PIN 5
#define TANK_ECHO_PIN 18

const float TANK_MIN_VALID_CM = 2.0f;
const float TANK_MAX_VALID_CM = 400.0f;

// Riego (1 rele)
#define RELAY_PIN 25
const char* PLANT_TYPE = "lechuga";

// Intervalos
const unsigned long TELEMETRY_INTERVAL_MS = 300000;      // 5 min
const unsigned long COMMAND_POLL_INTERVAL_MS = 300000;   // 5 min
const unsigned long ACTIVE_POLL_INTERVAL_MS = 5000;      // 5 s
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

bool irrigationActive = false;
unsigned long irrigationStartTime = 0;
unsigned long irrigationDurationMs = 0;
int irrigationEventId = 0;
String irrigationReason = "";

float lastValidDistanceCm = -1.0f;

String macAddress;
String topicTelemetryEnvironment;
String topicCommandsRequest;
String topicCommandsResponse;
String topicNotifications;

WiFiClientSecure wifiClient;
PubSubClient mqttClient(wifiClient);
WebServer server(80);

float readTankDistanceCm() {
  for (int attempt = 0; attempt < 3; attempt++) {
    digitalWrite(TANK_TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TANK_TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TANK_TRIG_PIN, LOW);

    long durationUs = pulseIn(TANK_ECHO_PIN, HIGH, 30000); // timeout ~30ms
    if (durationUs <= 0) {
      delay(15);
      continue;
    }

    // Distancia en cm: velocidad sonido aprox. 0.0343 cm/us, ida y vuelta /2
    float distance = (durationUs * 0.0343f) / 2.0f;

    // Filtro de valores físicamente improbables del HC-SR04.
    if (distance >= TANK_MIN_VALID_CM && distance <= TANK_MAX_VALID_CM) {
      return distance;
    }

    delay(15);
  }

  return -1.0f;
}

void setRelayState(bool active) {
  irrigationActive = active;
  // Reles tipicos son activos en LOW; ajusta si tu modulo es distinto
  digitalWrite(RELAY_PIN, active ? LOW : HIGH);
}

void sendNotification(const char* notificationType, const String& reason) {
  StaticJsonDocument<384> doc;
  doc["mac_address"] = macAddress;
  doc["esp32_ip"] = WiFi.localIP().toString();
  doc["event_id"] = irrigationEventId;
  doc["relay"] = 1;
  doc["plant_type"] = PLANT_TYPE;
  doc["notification_type"] = notificationType;
  doc["reason"] = reason;

  float humidity = dht.readHumidity();
  if (!isnan(humidity)) {
    // Campo legacy que backend usa como humedad_final en cierre de evento.
    doc["humedad_suelo"] = humidity;
  }

  JsonObject payload = doc.createNestedObject("payload");
  payload["relay_active"] = irrigationActive;
  payload["relay_reason"] = irrigationReason;

  char buffer[384];
  size_t n = serializeJson(doc, buffer, sizeof(buffer));
  mqttClient.publish(topicNotifications.c_str(), buffer, n);
}

void startIrrigation(int durationSeconds, int eventId, const String& reason) {
  setRelayState(true);
  irrigationStartTime = millis();
  irrigationDurationMs = (unsigned long)durationSeconds * 1000UL;
  irrigationEventId = eventId;
  irrigationReason = reason;

  Serial.printf("Relay ON for %d s | event %d | reason: %s\n", durationSeconds, eventId, reason.c_str());
  sendNotification("start", reason);
}

void stopIrrigation(const char* notificationType, const String& reason) {
  if (!irrigationActive && irrigationEventId == 0) {
    return;
  }

  setRelayState(false);
  unsigned long realDurationSec = (millis() - irrigationStartTime) / 1000UL;
  Serial.printf("Relay OFF | event %d | real_duration=%lu s | reason: %s\n", irrigationEventId, realDurationSec, reason.c_str());

  sendNotification(notificationType, reason);

  irrigationStartTime = 0;
  irrigationDurationMs = 0;
  irrigationEventId = 0;
  irrigationReason = "";
}

void publishEnvironmentTelemetry(float temperature, float humidity, float distanceCm) {
  StaticJsonDocument<384> doc;
  doc["mac_address"] = macAddress;
  doc["esp32_ip"] = WiFi.localIP().toString();
  doc["temperatura"] = temperature;
  doc["humedad_ambiente"] = humidity;

  float distanceToPublish = distanceCm;
  if (distanceToPublish < 0.0f && lastValidDistanceCm >= 0.0f) {
    distanceToPublish = lastValidDistanceCm;
  }

  // El backend acepta cualquiera de estos campos para tanque.
  if (distanceToPublish >= 0.0f) {
    doc["distancia"] = distanceToPublish;
    doc["nivel_deposito_cm"] = distanceToPublish;
  }

  char payload[384];
  size_t n = serializeJson(doc, payload, sizeof(payload));
  mqttClient.publish(topicTelemetryEnvironment.c_str(), payload, n);
}

void publishCommandRequest() {
  StaticJsonDocument<384> doc;
  doc["mac_address"] = macAddress;
  doc["esp32_ip"] = WiFi.localIP().toString();

  JsonArray zones = doc.createNestedArray("zones");
  JsonObject zone = zones.createNestedObject();
  zone["relay"] = 1;
  zone["plant_type"] = PLANT_TYPE;
  zone["active"] = irrigationActive;
  zone["event_id"] = irrigationEventId;

  char payload[384];
  size_t n = serializeJson(doc, payload, sizeof(payload));
  mqttClient.publish(topicCommandsRequest.c_str(), payload, n);
}

void handleCommandsResponse(const JsonDocument& responseDoc) {
  JsonArrayConst commands = responseDoc["commands"].as<JsonArrayConst>();

  for (JsonObjectConst cmd : commands) {
    int relay = cmd["relay"] | 0;
    if (relay != 1) {
      continue;
    }

    const char* command = cmd["command"] | "OFF";
    int duration = cmd["duration"] | 0;
    int eventId = cmd["event_id"] | 0;
    String reason = String((const char*)(cmd["reason"] | "Sin razon"));

    if (strcmp(command, "ON") == 0) {
      if (!irrigationActive || eventId != irrigationEventId) {
        startIrrigation(duration, eventId, reason);
      }
    } else {
      stopIrrigation("stop", reason);
    }
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String currentTopic = String(topic);
  String body;
  body.reserve(length);
  for (unsigned int i = 0; i < length; i++) {
    body += (char)payload[i];
  }

  if (currentTopic == topicCommandsResponse) {
    DynamicJsonDocument doc(2048);
    DeserializationError err = deserializeJson(doc, body);
    if (!err) {
      handleCommandsResponse(doc);
    } else {
      Serial.println("Error parsing commands response JSON");
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
    String clientId = "esp32-env-" + macAddress;
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

void checkIrrigationTimeout() {
  if (!irrigationActive) {
    return;
  }

  unsigned long elapsed = millis() - irrigationStartTime;
  if (elapsed >= irrigationDurationMs) {
    stopIrrigation("completed", "Duracion completada");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  dht.begin();

  pinMode(TANK_TRIG_PIN, OUTPUT);
  pinMode(TANK_ECHO_PIN, INPUT);

  pinMode(RELAY_PIN, OUTPUT);
  // Rele apagado por defecto (activo LOW)
  digitalWrite(RELAY_PIN, HIGH);

  connectWiFi();
  macAddress = WiFi.macAddress();

  syncSystemTime();

  if (MQTT_TEST_INSECURE) {
    wifiClient.setInsecure();
    Serial.println("MQTT TLS test mode: setInsecure enabled");
  } else {
    wifiClient.setCACert(MQTT_CA_CERT);
    wifiClient.setHandshakeTimeout(MQTT_HANDSHAKE_TIMEOUT_SEC * 1000);  // Convert to milliseconds
  }

  topicTelemetryEnvironment = "esp32/" + macAddress + "/telemetry/environment";
  topicCommandsRequest = "esp32/" + macAddress + "/commands/request";
  topicCommandsResponse = "esp32/" + macAddress + "/commands/response";
  topicNotifications = "esp32/" + macAddress + "/notifications";

  mqttClient.setServer(mqttHost, mqttPort);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(4096);
  mqttClient.setKeepAlive(MQTT_KEEPALIVE_SEC);
  mqttClient.setSocketTimeout(MQTT_SOCKET_TIMEOUT_SEC);

  server.on("/status", HTTP_GET, []() {
    unsigned long remaining = 0;
    if (irrigationActive) {
      unsigned long elapsed = millis() - irrigationStartTime;
      remaining = (irrigationDurationMs > elapsed) ? (irrigationDurationMs - elapsed) / 1000UL : 0;
    }

    String statusJson = "{\"status\":\"online\",\"ip\":\"" + WiFi.localIP().toString() +
                        "\",\"irrigation_active\":" + String(irrigationActive ? "true" : "false") +
                        ",\"time_remaining\":" + String(remaining) + "}";
    server.send(200, "application/json", statusJson);
  });

  server.begin();
  Serial.println("HTTP status endpoint ready");
}

void loop() {
  server.handleClient();

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (!mqttClient.connected()) {
    connectMqtt();
  }

  mqttClient.loop();
  checkIrrigationTimeout();

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  float distanceCm = readTankDistanceCm();
  if (distanceCm >= 0.0f) {
    lastValidDistanceCm = distanceCm;
  }

  static unsigned long lastTelemetry = 0;
  if (millis() - lastTelemetry >= TELEMETRY_INTERVAL_MS || lastTelemetry == 0) {
    if (!isnan(temperature) && !isnan(humidity)) {
      publishEnvironmentTelemetry(temperature, humidity, distanceCm);
      if (distanceCm >= 0.0f) {
        Serial.printf("Telemetry env -> T=%.1f H=%.1f Dist=%.1f\n", temperature, humidity, distanceCm);
      } else if (lastValidDistanceCm >= 0.0f) {
        Serial.printf("Telemetry env -> T=%.1f H=%.1f Dist=-1.0 (fallback %.1f)\n", temperature, humidity, lastValidDistanceCm);
      } else {
        Serial.printf("Telemetry env -> T=%.1f H=%.1f Dist=-1.0 (sin fallback)\n", temperature, humidity);
      }
    } else {
      Serial.println("DHT read failed, telemetry skipped");
    }
    lastTelemetry = millis();
  }

  static unsigned long lastCommandPoll = 0;
  unsigned long pollInterval = irrigationActive ? ACTIVE_POLL_INTERVAL_MS : COMMAND_POLL_INTERVAL_MS;
  if (millis() - lastCommandPoll >= pollInterval || lastCommandPoll == 0) {
    publishCommandRequest();
    lastCommandPoll = millis();
  }

  delay(50);
}
