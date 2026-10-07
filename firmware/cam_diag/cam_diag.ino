/* DoorbellCam hardware diagnostic: SCCB (camera I2C) bus scanner.
 *
 * Flash this sketch (instead of doorbell_cam.ino) when the main firmware
 * reports "camera init FAILED" — it bit-bangs the SCCB bus on GPIO26 (SDA)
 * / GPIO27 (SCL), probes every 7-bit address, and prints ACKs over serial
 * at 115200 baud. Expect 0x30 (OV2640). No ACKs at all means the sensor is
 * unseated, unpowered, or the board is a PDN-variant needing a pin tweak.
 */
#include <Arduino.h>

#define SDA_PIN 26
#define SCL_PIN 27

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("\n[SCAN] bit-bang SCCB scan on camera bus (GPIO26/27)");
  pinMode(SDA_PIN, OUTPUT); digitalWrite(SDA_PIN, HIGH);
  pinMode(SCL_PIN, OUTPUT); digitalWrite(SCL_PIN, HIGH);
  delay(50);

  int found = 0;
  for (uint8_t addr = 1; addr < 120; addr++) {
    // START
    digitalWrite(SDA_PIN, HIGH); digitalWrite(SCL_PIN, HIGH); delayMicroseconds(5);
    digitalWrite(SDA_PIN, LOW);  delayMicroseconds(5); digitalWrite(SCL_PIN, LOW);
    // write address (8-bit: addr<<1 | W)
    uint8_t b = addr << 1;
    bool ack = true;
    for (int bit = 7; bit >= 0; bit--) {
      digitalWrite(SDA_PIN, (b >> bit) & 1 ? HIGH : LOW);
      delayMicroseconds(4);
      digitalWrite(SCL_PIN, HIGH); delayMicroseconds(4);
      digitalWrite(SCL_PIN, LOW);  delayMicroseconds(4);
    }
    pinMode(SDA_PIN, INPUT_PULLUP); delayMicroseconds(4);
    digitalWrite(SCL_PIN, HIGH); delayMicroseconds(4);
    ack = digitalRead(SDA_PIN) == LOW;   // ACK = low
    digitalWrite(SCL_PIN, LOW);
    pinMode(SDA_PIN, OUTPUT);
    // STOP
    digitalWrite(SDA_PIN, LOW); delayMicroseconds(4);
    digitalWrite(SCL_PIN, HIGH); delayMicroseconds(4);
    digitalWrite(SDA_PIN, HIGH); delayMicroseconds(4);

    if (ack) {
      Serial.printf("[SCAN] ACK at 7-bit addr 0x%02X\n", addr);
      found++;
    }
  }
  Serial.printf("[SCAN] done, %d device(s) found\n", found);
}

void loop() { delay(1000); }
