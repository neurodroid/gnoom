#include <Arduino.h>

constexpr uint8_t ENCODER_A = 2;
constexpr uint8_t ENCODER_B = 7;
constexpr uint8_t QUEUE_SIZE = 128;

volatile uint8_t steps[QUEUE_SIZE];
volatile uint8_t read_index = 0;
volatile uint8_t write_index = 0;

void a_change()
{
  const uint8_t next_index = (write_index + 1) % QUEUE_SIZE;
  if (next_index == read_index) {
    return; // Keep the queued steps when the encoder outruns the serial link.
  }

  const int channel_a = digitalRead(ENCODER_A);
  const int channel_b = digitalRead(ENCODER_B);
  steps[write_index] = channel_a == channel_b ? 0x00 : 0x01;
  write_index = next_index;
}

void setup()
{
  pinMode(ENCODER_A, INPUT);
  pinMode(ENCODER_B, INPUT);
  Serial.begin(115200);
  attachInterrupt(digitalPinToInterrupt(ENCODER_A), a_change, CHANGE);
}

void loop()
{
  while (read_index != write_index && Serial.availableForWrite() > 0) {
    const uint8_t step = steps[read_index];
    read_index = (read_index + 1) % QUEUE_SIZE;
    Serial.write(step);
  }
}
