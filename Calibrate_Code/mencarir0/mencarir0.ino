#define RL_VALUE 5.0
#define SENSOR_PIN 34

void setup() {
  Serial.begin(9600);
  Serial.println("=== Kalibrasi MQ-2 (ESP32) ===");
  Serial.println("Letakkan sensor di udara bersih...");
}

void loop() {
  float adc_sum = 0;
  for (int i = 0; i < 100; i++) {
    adc_sum += analogRead(SENSOR_PIN);
    delay(1);
  }

  float adc_avg = adc_sum / 100.0;
  float sensor_volt = (adc_avg / 4095.0) * 5.0;  // untuk ESP32
  float RS_air = RL_VALUE * (5.0 - sensor_volt) / sensor_volt;

  Serial.print("ADC: ");
  Serial.print(adc_avg);
  Serial.print(" | Tegangan: ");
  Serial.print(sensor_volt, 3);
  Serial.print(" V | R0 = ");
  Serial.println(RS_air, 2);

  delay(1000);
}
