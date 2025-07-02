#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <ArduinoMqttClient.h>
#include <DHT.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP280.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h>
#include "time.h"

// ================== Konfigurasi WiFi ==================
const char* ssid = "A_STATION";
const char* password = "agungx609soeltani";

// ================== Konfigurasi MQTT (WSS via Cloudflare) ==================
const char* mqtt_server = "mqtt.nultragroup.icu";
const int mqtt_port = 443;
const char* mqtt_user = "nultra";
const char* mqtt_pass = "nultragroup";
const char* mqtt_client_id = "esp32-alat-kualitas-udara-01";
const char* mqtt_topic_publish = "iot/kualitas_udara/alat01/data";
const char* mqtt_topic_subscribe = "iot/kualitas_udara/alat01/perintah";

// ================== Sensor & Pin ==================
#define DHTPIN 14
#define DHTTYPE DHT11
#define MQ2_PIN 34
#define LED_HIJAU 25
#define LED_KUNING 27
#define LED_MERAH 26
#define BUZZER_PIN 33

// ================== Kalibrasi MQ2 ==================
#define R0 3.93
#define RL_VALUE 5.0
#define ADC_RESOLUTION 4095.0
#define SMOKE_SLOPE -0.39
#define SMOKE_INTERCEPT_Y 3.4
#define SMOKE_INTERCEPT_X 200
const int THRESHOLD_SEDANG = 300;
const int THRESHOLD_BURUK = 700;
const long PUBLISH_INTERVAL = 60000;

// ================== NTP (Waktu Internet) ==================
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 3600 * 7;
const int daylightOffset_sec = 0;

// ================== Objek ==================
WiFiClientSecure net;
MqttClient mqttClient(net);
DHT dht(DHTPIN, DHTTYPE);
Adafruit_BMP280 bmp;
LiquidCrystal_I2C lcd(0x27, 16, 2);

unsigned long lastMsg = 0;
char lcd_line1_buffer[17];

// ================== Setup ==================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== SYSTEM BOOTING... ===");

  pinMode(LED_HIJAU, OUTPUT);
  pinMode(LED_KUNING, OUTPUT);
  pinMode(LED_MERAH, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  lcd.begin(); lcd.backlight();
  lcd.setCursor(0, 0); lcd.print("Booting...");

  Wire.begin();
  dht.begin();

  if (!bmp.begin(0x76)) {
    Serial.println("[ERROR] BMP280 tidak ditemukan!");
    lcd.clear(); lcd.print("Err: BMP280");
    while (1);
  }

  // WiFi
  WiFi.begin(ssid, password);
  Serial.print("Menghubungkan WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\n[OK] WiFi Terhubung");
  Serial.print("IP: "); Serial.println(WiFi.localIP());
  lcd.clear(); lcd.print("WiFi OK");

  // NTP Time
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  Serial.println("Waktu sinkron NTP OK");

  // TLS insecure untuk development
  net.setInsecure();

  // MQTT Setup
  mqttClient.setId(mqtt_client_id);
  mqttClient.setUsernamePassword(mqtt_user, mqtt_pass);
  mqttClient.onMessage(onMqttMessage);

  Serial.print("MQTT Connect...");
  if (!mqttClient.connect(mqtt_server, mqtt_port)) {
    Serial.print(" Gagal, code: ");
    Serial.println(mqttClient.connectError());
    lcd.clear(); lcd.print("MQTT Error");
    while (1);
  }

  Serial.println(" MQTT Connected!");
  mqttClient.subscribe(mqtt_topic_subscribe);
  Serial.println("Subscribed to command topic.");
}

// ================== Loop ==================
void loop() {
  mqttClient.poll();

  unsigned long now = millis();
  if (now - lastMsg > PUBLISH_INTERVAL) {
    lastMsg = now;

    float suhu = dht.readTemperature();
    float kelembaban = dht.readHumidity();
    float tekanan = bmp.readPressure() / 100.0F;
    int mq2_raw = analogRead(MQ2_PIN);

    if (isnan(suhu) || isnan(kelembaban)) {
      Serial.println("[ERROR] Gagal baca DHT");
      return;
    }

    double vrl = ((double)mq2_raw / ADC_RESOLUTION) * RL_VALUE;
    double rs_ro_ratio = ((RL_VALUE - vrl) / vrl) / R0;
    double ppm = pow(10, ((log10(rs_ro_ratio) - SMOKE_INTERCEPT_Y) / SMOKE_SLOPE) + log10(SMOKE_INTERCEPT_X));

    struct tm timeinfo;
    if (!getLocalTime(&timeinfo)) {
      Serial.println("[ERROR] Waktu tidak tersedia");
      return;
    }

    char timeString[20];
    strftime(timeString, sizeof(timeString), "%Y-%m-%d %H:%M:%S", &timeinfo);

    StaticJsonDocument<256> doc;
    doc["timestamp"] = timeString;
    doc["suhu"] = suhu;
    doc["kelembaban"] = kelembaban;
    doc["tekanan"] = tekanan;
    doc["mq2_raw"] = mq2_raw;
    doc["gas_ppm"] = ppm;

    char buffer[256];
    serializeJson(doc, buffer);

    Serial.println("[PUBLISH]");
    Serial.println(buffer);

    mqttClient.beginMessage(mqtt_topic_publish);
    mqttClient.print(buffer);
    mqttClient.endMessage();

    snprintf(lcd_line1_buffer, sizeof(lcd_line1_buffer), "S:%.1f H:%.1f", suhu, kelembaban);
    lcd.setCursor(0, 0); lcd.print(lcd_line1_buffer);
    lcd.setCursor(0, 1); lcd.print("PPM: "); lcd.print(ppm); lcd.print("   ");

    updatePhysicalOutput(ppm);
  }
}

// ================== MQTT Message Handler ==================
void onMqttMessage(int messageSize) {
  String topic = mqttClient.messageTopic();
  String msg = "";

  while (mqttClient.available()) {
    msg += (char)mqttClient.read();
  }

  Serial.print("[MQTT CMD] "); Serial.print(topic);
  Serial.print(" = "); Serial.println(msg);

  if (msg == "BUZZER_ON") {
    digitalWrite(BUZZER_PIN, HIGH);
  } else if (msg == "BUZZER_OFF") {
    digitalWrite(BUZZER_PIN, LOW);
  }
}

// ================== Output Kontrol ==================
void updatePhysicalOutput(double ppmValue) {
  if (ppmValue >= THRESHOLD_BURUK) {
    digitalWrite(LED_MERAH, HIGH);
    digitalWrite(LED_KUNING, LOW);
    digitalWrite(LED_HIJAU, LOW);
    digitalWrite(BUZZER_PIN, HIGH);
  } else if (ppmValue >= THRESHOLD_SEDANG) {
    digitalWrite(LED_MERAH, LOW);
    digitalWrite(LED_KUNING, HIGH);
    digitalWrite(LED_HIJAU, LOW);
    digitalWrite(BUZZER_PIN, LOW);
  } else {
    digitalWrite(LED_MERAH, LOW);
    digitalWrite(LED_KUNING, LOW);
    digitalWrite(LED_HIJAU, HIGH);
    digitalWrite(BUZZER_PIN, LOW);
  }
}
