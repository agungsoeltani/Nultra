/*
 * Kode untuk Memantau Kualitas Udara Umum (Estimasi PPM Asap)
 * Menggunakan nilai R0 yang sudah dikalibrasi.
 */

// === Parameter yang perlu disesuaikan ===
// Masukkan nilai R0 yang Anda dapatkan dari proses kalibrasi
#define R0 3.93 // Ganti dengan nilai R0 Anda!

// Nilai resistor beban pada modul (biasanya 5.0 kΩ)
#define RL_VALUE 5.0

// Pin analog yang terhubung ke sensor
#define SENSOR_PIN 34

// Parameter kurva gas Asap (Smoke) dari datasheet
// Diambil dari dua titik: (x1, y1) = (200, 3.4) dan (x2, y2) = (10000, 0.7)
#define SMOKE_SLOPE -0.39
#define SMOKE_INTERCEPT_Y 3.4 // Rs/R0 value at 200ppm
#define SMOKE_INTERCEPT_X 200 // 200ppm

void setup() {
  Serial.begin(9600);
}

void loop() {
  float sensor_volt;
  float RS_gas;
  float ratio;
  float sensor_value = analogRead(SENSOR_PIN);

  // Konversi ADC ke tegangan
  sensor_volt = (sensor_value / 1023.0) * 5.0;

  // Hitung RS
  RS_gas = RL_VALUE * (5.0 - sensor_volt) / sensor_volt;

  // Hitung rasio RS_gas / R0
  ratio = RS_gas / R0;

  // Hitung PPM menggunakan rumus dari kurva log-log untuk Asap
  double ppm = SMOKE_INTERCEPT_X * pow(ratio / SMOKE_INTERCEPT_Y, 1.0 / SMOKE_SLOPE);

  Serial.print("Rasio (RS/R0): ");
  Serial.print(ratio);
  Serial.print("\t");
  Serial.print("Estimasi Polusi Udara (ppm Asap): ");
  Serial.println(ppm);

  delay(1000);
}