/*
 * Kode untuk Kalibrasi Sensor MQ-2
 * Tujuan: Menentukan nilai R0 (resistansi sensor di udara bersih)
 */

// Definisikan nilai resistor beban (Load Resistor) pada modul MQ-2 Anda.
// Nilai ini biasanya 5 kΩ (kilo-ohm) untuk modul yang umum di pasaran.
#define RL_VALUE 5.0

// Pin analog yang terhubung ke sensor
#define SENSOR_PIN 34

void setup() {
  Serial.begin(9600);
  Serial.println("Kalibrasi Sensor MQ-2...");
  Serial.println("Letakkan sensor di udara bersih dan tunggu beberapa menit.");
  Serial.println("Nilai R0 yang stabil akan muncul.");
}

void loop() {
  float sensor_volt;
  float RS_air; // Resistansi sensor di udara bersih
  float sensor_value;

  // Baca nilai ADC dari sensor sebanyak 100 kali untuk mendapatkan rata-rata
  float sum = 0;
  for(int i = 0; i < 100; i++) {
    sum += analogRead(SENSOR_PIN);
    delay(1);
  }
  sensor_value = sum / 100.0;

  // Konversi nilai ADC (0-1023) ke tegangan (0-5V)
  sensor_volt = (sensor_value / 1023.0) * 5.0;

  // Hitung nilai RS menggunakan rumus dari datasheet
  // RS = RL * (V_c - V_out) / V_out
  // V_c = 5V
  RS_air = RL_VALUE * (5.0 - sensor_volt) / sensor_volt;

  // Tampilkan nilai R0 (RS_air)
  Serial.print("Nilai R0 = ");
  Serial.println(RS_air);

  delay(1000); // Tunggu 1 detik sebelum pengukuran berikutnya
}