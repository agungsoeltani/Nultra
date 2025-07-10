#include <Servo.h>

Servo myServo;  // buat objek servo

void setup() {
  myServo.attach(9);  // sambungkan ke pin D9
}

void loop() {
  myServo.write(90);      // gerakkan ke 90 derajat
  delay(2000);            // tunggu 5 detik
  myServo.write(0);       // kembali ke 0 derajat
  delay(1000);            // tunggu 1 detik sebelum mengulang
}
