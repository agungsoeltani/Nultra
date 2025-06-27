// ===================================================================== //
//       KODE FINAL - PERANGKAT SENSOR KUALITAS UDARA (ESP32)            //
//            (DENGAN TAMPILAN MONITOR & TELNET DETAIL)                  //
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
#include <math.h>
#include "time.h"

// 2. KONFIGURASI (Tetap sama)
// ... (Semua konfigurasi Anda sebelumnya diletakkan di sini) ...
// -- Konfigurasi Jaringan & MQTT --
const char* ssid = "Sahroni";
const char* password = "nursahroni";
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* mqtt_client_id = "esp32-alat-kualitas-udara-01";
const char* mqtt_topic_publish = "iot/kualitas_udara/alat01/data";
const char* mqtt_topic_subscribe = "iot/kualitas_udara/alat01/perintah";
// -- Konfigurasi Pin --
#define DHTPIN 14
#define DHTTYPE DHT11
#define MQ2_PIN 34
#define LED_HIJAU 25
#define LED_KUNING 27
#define LED_MERAH 26
#define BUZZER_PIN 33
// -- Konfigurasi Sensor MQ-2 untuk PPM --
#define R0 3.93
#define RL_VALUE 5.0
#define ADC_RESOLUTION 4095.0
#define SMOKE_SLOPE -0.39
#define SMOKE_INTERCEPT_Y 3.4
#define SMOKE_INTERCEPT_X 200
// -- Konfigurasi Ambang Batas berdasarkan PPM --
const int THRESHOLD_SEDANG = 300;
const int THRESHOLD_BURUK  = 700;
// -- Konfigurasi Waktu (NTP) --
const char* ntpServer = "pool.ntp.org";
const long  gmtOffset_sec = 3600 * 7;
const int   daylightOffset_sec = 0;
const long PUBLISH_INTERVAL = 60000;


// 3. INISIALISASI OBJEK (Tetap sama)
WiFiClient espClient;
PubSubClient client(espClient);
DHT dht(DHTPIN, DHTTYPE);
Adafruit_BMP280 bmp;
LiquidCrystal_I2C lcd(0x27, 16, 2);
WiFiServer telnetServer(23);
WiFiClient telnetClient;

// 4. Variabel Global & Deklarasi Fungsi (Hapus deklarasi bacaPpmAsap)
unsigned long lastMsg = 0;
char lcd_line1_buffer[17] = "STATUS: OK";
void callback(char* topic, byte* payload, unsigned int length);
void setup_wifi();
void reconnect_mqtt();
void updatePhysicalOutput(double ppmValue, float suhu);
void handleTelnet();
void printToAll(const String& message, bool newline = false);


// 5. FUNGSI SETUP (Tetap sama)
void setup() {
  Serial.begin(115200);
  pinMode(LED_HIJAU, OUTPUT); pinMode(LED_KUNING, OUTPUT); pinMode(LED_MERAH, OUTPUT); pinMode(BUZZER_PIN, OUTPUT);
  lcd.begin(); lcd.backlight(); lcd.setCursor(0, 0); lcd.print("Sistem Starting");
  Wire.begin(); dht.begin();
  if (!bmp.begin(0x76)) {
    printToAll("Error: BMP280 tidak ditemukan!", true);
    lcd.clear(); lcd.print("Error: BMP280"); while (1);
  }
  setup_wifi();
  telnetServer.begin();
  printToAll("Server Telnet dimulai!", true);
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  printToAll("Waktu NTP telah dikonfigurasi.", true);
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}


// 6. FUNGSI LOOP UTAMA
void loop() {
  handleTelnet(); 

  if (!client.connected()) {
    reconnect_mqtt();
  }
  client.loop();

  unsigned long now = millis();
  if (now - lastMsg > PUBLISH_INTERVAL) {
    lastMsg = now;

    // --- PERUBAHAN: SEMUA LOGIKA PENGUKURAN DAN TAMPILAN ADA DI SINI ---

    // 1. Lakukan semua pengukuran sensor
    float suhu = dht.readTemperature();
    float lembab = dht.readHumidity();
    float tekanan = bmp.readPressure() / 100.0F;
    
    // Logika dari bacaPpmAsap() dipindahkan ke sini
    float mq2_adc_value = analogRead(MQ2_PIN);
    float rs_gas = 0;
    float ratio = 0;
    double ppmValue = 0;

    if (mq2_adc_value > 0) { // Mencegah pembagian dengan nol
        rs_gas = RL_VALUE * (ADC_RESOLUTION / mq2_adc_value - 1.0);
        ratio = rs_gas / R0;
        ppmValue = SMOKE_INTERCEPT_X * pow(ratio / SMOKE_INTERCEPT_Y, 1.0 / SMOKE_SLOPE);
    }

    // Dapatkan waktu saat ini
    struct tm timeinfo;
    if(!getLocalTime(&timeinfo)){
      printToAll("Gagal mendapatkan waktu lokal", true);
      return;
    }
    time_t epochTime = mktime(&timeinfo);

    // 2. Tentukan status berdasarkan data
    String status_udara;
    String aksi_sistem;
    if (ppmValue >= THRESHOLD_BURUK) {
        status_udara = "BURUK";
        aksi_sistem = "LED Merah ON & Buzzer ON";
    } else if (ppmValue >= THRESHOLD_SEDANG) {
        status_udara = "SEDANG";
        aksi_sistem = "LED Kuning ON";
    } else {
        status_udara = "BAIK";
        aksi_sistem = "LED Hijau ON";
    }

    // 3. Cetak Laporan Status yang Terstruktur
    char timeStr[20];
    strftime(timeStr, sizeof(timeStr), "%H:%M:%S", &timeinfo);

    printToAll("\n=============================================", true);
    printToAll("[" + String(timeStr) + "] LAPORAN STATUS & PENGUKURAN SENSOR", true);
    printToAll("=============================================", true);
    
    printToAll("--- Status Sistem ---", true);
    printToAll("  Koneksi WiFi   : Terhubung ke '" + String(ssid) + "'", true);
    printToAll("  Alamat IP      : " + WiFi.localIP().toString(), true);
    printToAll("  Koneksi MQTT   : Terhubung ke " + String(mqtt_server), true);
    printToAll("", true); // Spasi

    printToAll("--- Pembacaan Sensor ---", true);
    printToAll("  Suhu & Kelembaban (DHT11):", true);
    printToAll("    - Suhu       : " + String(suhu, 1) + " C", true);
    printToAll("    - Kelembaban : " + String(lembab, 1) + " %", true);
    printToAll("  Tekanan Udara (BMP280):", true);
    printToAll("    - Tekanan    : " + String(tekanan, 2) + " hPa", true);
    printToAll("  Sensor Gas (MQ-2):", true);
    printToAll("    - Nilai ADC  : " + String(mq2_adc_value), true);
    printToAll("    - Res. Sensor (Rs) : " + String(rs_gas, 2) + " kOhm", true);
    printToAll("    - Rasio (Rs/R0)    : " + String(ratio, 2), true);
    printToAll("    -> Konsentrasi PPM  : " + String(ppmValue, 2) + " ppm", true);
    printToAll("", true); // Spasi

    printToAll("--- Analisis & Aksi ---", true);
    printToAll("  Status Udara   : " + status_udara, true);
    printToAll("  Aksi Sistem    : " + aksi_sistem, true);
    printToAll("---------------------------------------------", true);


    // 4. Update output fisik (LCD & LED)
    updatePhysicalOutput(ppmValue, suhu);

    // 5. Kirim data ke MQTT
    StaticJsonDocument<256> doc;
    doc["suhu"] = suhu;
    doc["kelembaban"] = lembab;
    doc["tekanan"] = tekanan;
    doc["gas_ppm"] = ppmValue; 
    doc["timestamp"] = epochTime;

    char jsonBuffer[256];
    serializeJson(doc, jsonBuffer);

    client.publish(mqtt_topic_publish, jsonBuffer);
    printToAll("-> Pesan JSON dikirim ke MQTT.", true);
    printToAll("=============================================\n", true);
  }
}

// 7. FUNGSI-FUNGSI BANTUAN (Fungsi `bacaPpmAsap` sudah tidak diperlukan dan bisa dihapus)
// ... (Semua fungsi bantuan lainnya seperti `handleTelnet`, `printToAll`, `updatePhysicalOutput`, `callback`, `reconnect_mqtt`, `setup_wifi` tetap sama) ...
void handleTelnet(){if(telnetServer.hasClient()){if(telnetClient&&telnetClient.connected()){telnetClient.stop();}telnetClient=telnetServer.available();telnetClient.println("\nWelcome to ESP32 Air Quality Monitor!");telnetClient.println("------------------------------------");}if(telnetClient&&telnetClient.connected()&&telnetClient.available()){while(telnetClient.available()){telnetClient.read();}}}
void printToAll(const String& message,bool newline){if(newline){Serial.println(message);if(telnetClient&&telnetClient.connected()){telnetClient.println(message);}}else{Serial.print(message);if(telnetClient&&telnetClient.connected()){telnetClient.print(message);}}}
void updatePhysicalOutput(double ppmValue,float suhu){lcd.clear();lcd.setCursor(0,0);lcd.print(lcd_line1_buffer);lcd.setCursor(0,1);lcd.print("Suhu:"+String(suhu,1)+"C Gas:"+String((int)ppmValue)+"ppm");digitalWrite(LED_HIJAU,LOW);digitalWrite(LED_KUNING,LOW);digitalWrite(LED_MERAH,LOW);noTone(BUZZER_PIN);if(ppmValue>=THRESHOLD_BURUK){digitalWrite(LED_MERAH,HIGH);tone(BUZZER_PIN,1500,200);}else if(ppmValue>=THRESHOLD_SEDANG){digitalWrite(LED_KUNING,HIGH);}else{digitalWrite(LED_HIJAU,HIGH);}}
void callback(char* topic,byte* payload,unsigned int length){printToAll("Pesan diterima pada topik: "+String(topic),true);char message[length+1];memcpy(message,payload,length);message[length]='\0';printToAll("Payload: "+String(message),true);StaticJsonDocument<256> doc;DeserializationError error=deserializeJson(doc,message);if(error){printToAll("deserializeJson() gagal: "+String(error.c_str()),true);return;}const char* displayText=doc["display_text"];if(displayText){strncpy(lcd_line1_buffer,displayText,16);lcd_line1_buffer[16]='\0';if(strstr(displayText,"BAHAYA")||strstr(displayText,"WASPADA")){tone(BUZZER_PIN,2000,1000);}}}
void reconnect_mqtt(){while(!client.connected()){printToAll("Mencoba koneksi MQTT...",false);if(client.connect(mqtt_client_id)){printToAll(" terhubung!",true);client.subscribe(mqtt_topic_subscribe);}else{printToAll(" gagal, rc="+String(client.state())+". Coba lagi 5 detik",true);delay(5000);}}}
void setup_wifi(){lcd.clear();lcd.print("Hubungkan WiFi..");WiFi.begin(ssid,password);while(WiFi.status()!=WL_CONNECTED){delay(500);Serial.print(".");}printToAll("\nWiFi terhubung!",true);printToAll("Alamat IP: "+WiFi.localIP().toString(),true);lcd.clear();lcd.print("WiFi Terhubung!");lcd.setCursor(0,1);lcd.print(WiFi.localIP());delay(2000);}