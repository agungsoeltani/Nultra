// ===================================================================== //
//  KODE LENGKAP - PROYEK KUALITAS UDARA DENGAN FEEDBACK AI VIA MQTT     //
//                  (VERSI FINAL YANG DIPERBAIKI)                        //
// ===================================================================== //

// 1. PUSTAKA (LIBRARY)
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP280.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// 2. KONFIGURASI
// -- Konfigurasi Jaringan & MQTT --
const char* ssid = "Sahroni";
const char* password = "nursahroni";
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* mqtt_client_id = "esp32-alat-kualitas-udara-01";
const char* mqtt_topic_publish = "iot/kualitas_udara/alat01/data";
const char* mqtt_topic_subscribe = "iot/kualitas_udara/alat01/perintah";

// -- Konfigurasi Pin (PERBAIKAN: Spasi sudah dirapikan) --
#define DHTPIN 14
#define DHTTYPE DHT11
#define MQ2_PIN 34
#define LED_HIJAU 25
#define LED_KUNING 27
#define LED_MERAH 26
#define BUZZER_PIN 33

// -- Konfigurasi Ambang Batas LOKAL (HARUS DISESUAIKAN) --
const int THRESHOLD_SEDANG = 400;
const int THRESHOLD_BURUK  = 700;
const long PUBLISH_INTERVAL = 60000; // 1 menit

// 3. INISIALISASI OBJEK
WiFiClient espClient;
PubSubClient client(espClient);
DHT dht(DHTPIN, DHTTYPE);
Adafruit_BMP280 bmp;
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Variabel Global
unsigned long lastMsg = 0;
char lcd_line1_buffer[17] = "STATUS: OK";

// Deklarasi fungsi
void callback(char* topic, byte* payload, unsigned int length);
void setup_wifi();
void reconnect_mqtt();
void updatePhysicalOutput(int nilai_gas, float suhu);

// 4. FUNGSI SETUP
void setup() {
  Serial.begin(115200);
  pinMode(LED_HIJAU, OUTPUT); pinMode(LED_KUNING, OUTPUT); pinMode(LED_MERAH, OUTPUT); pinMode(BUZZER_PIN, OUTPUT);
  
  // PERBAIKAN: Menggunakan lcd.init() bukan lcd.begin()
  lcd.begin();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Sistem Starting");

  Wire.begin();
  dht.begin();
  if (!bmp.begin(0x76)) {
    Serial.println("Error: BMP280 tidak ditemukan!");
    lcd.clear(); lcd.print("Error: BMP280"); while (1);
  }

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

// 5. FUNGSI LOOP UTAMA
void loop() {
  if (!client.connected()) {
    reconnect_mqtt();
  }
  client.loop();

  unsigned long now = millis();
  if (now - lastMsg > PUBLISH_INTERVAL) {
    lastMsg = now;

    float suhu = dht.readTemperature();
    float lembab = dht.readHumidity();
    float tekanan = bmp.readPressure() / 100.0F;
    int nilai_gas = analogRead(MQ2_PIN);

    if (isnan(suhu) || isnan(lembab)) {
      Serial.println("Gagal baca DHT!");
      return;
    }

    updatePhysicalOutput(nilai_gas, suhu);

    StaticJsonDocument<256> doc;
    doc["suhu"] = suhu;
    doc["kelembaban"] = lembab;
    doc["tekanan"] = tekanan;
    doc["nilai_gas"] = nilai_gas;

    char jsonBuffer[256];
    serializeJson(doc, jsonBuffer);

    client.publish(mqtt_topic_publish, jsonBuffer);
    Serial.println("Pesan terkirim ke MQTT.");
  }
}

// 6. FUNGSI-FUNGSI BANTUAN
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Pesan diterima pada topik: ");
  Serial.println(topic);

  char message[length + 1];
  memcpy(message, payload, length);
  message[length] = '\0';
  Serial.print("Payload: ");
  Serial.println(message);

  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, message);

  if (error) {
    Serial.print("deserializeJson() gagal: ");
    Serial.println(error.c_str());
    return;
  }

  const char* displayText = doc["display_text"]; 
  if (displayText) {
    strncpy(lcd_line1_buffer, displayText, 16);
    lcd_line1_buffer[16] = '\0';
    
    Serial.print("Teks untuk ditampilkan di LCD: ");
    Serial.println(lcd_line1_buffer);
    
    if (strstr(displayText, "BAHAYA") || strstr(displayText, "WASPADA TINGGI")) {
        tone(BUZZER_PIN, 2000, 1000);
    }
  }
} // PERBAIKAN: Tanda kurung kurawal '}' yang berlebih sudah dihapus.

void reconnect_mqtt() {
  while (!client.connected()) {
    Serial.print("Mencoba koneksi MQTT...");
    if (client.connect(mqtt_client_id)) {
      Serial.println("terhubung!");
      client.subscribe(mqtt_topic_subscribe);
      Serial.print("Subscribe ke topik: "); Serial.println(mqtt_topic_subscribe);
    } else {
      Serial.print("gagal, rc="); Serial.print(client.state()); Serial.println(" coba lagi 5 detik");
      delay(5000);
    }
  }
}

void updatePhysicalOutput(int nilai_gas, float suhu) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(lcd_line1_buffer);
  
  lcd.setCursor(0, 1);
  lcd.print("Suhu:" + String(suhu, 1) + "C Gas:" + String(nilai_gas));

  digitalWrite(LED_HIJAU, LOW); digitalWrite(LED_KUNING, LOW); digitalWrite(LED_MERAH, LOW);
  noTone(BUZZER_PIN);
  
  if (nilai_gas >= THRESHOLD_BURUK) {
    digitalWrite(LED_MERAH, HIGH);
    tone(BUZZER_PIN, 1500, 200);
  } else if (nilai_gas >= THRESHOLD_SEDANG) {
    digitalWrite(LED_KUNING, HIGH);
  } else {
    digitalWrite(LED_HIJAU, HIGH);
  }
}

void setup_wifi() {
  lcd.clear(); lcd.print("Hubungkan WiFi..");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\nWiFi terhubung!");
  lcd.clear();
  lcd.print("WiFi Terhubung!");
  delay(1500);
}