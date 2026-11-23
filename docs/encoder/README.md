# Rotary encoder hardware and calibration

The track uses a US Digital **E6-2500-472-IE-S-D-D-3** incremental optical kit encoder. The `2500` specifies cycles per shaft revolution, `472` specifies a 12 mm mounting bore, `IE` adds the index output, and `S` selects 5 V TTL single-ended outputs. `D-D-3` specifies the standard cover and base and individual packaging with assembly tools. [US Digital E6 product page](https://www.usdigital.com/products/encoders/incremental/kit/e6/) · [E6 datasheet and ordering guide](https://www.usdigital.com/assets/datasheets/datasheet-E6.pdf#page=12)

## Arduino wiring and direction

The five-pin `S` version takes a nominal 5 V DC supply (4.5–5.5 V) and draws 54 mA typical, 62 mA maximum with the outputs unloaded at this resolution. Check the pin-1 marking on the connector before wiring. [E6 electrical specifications](https://www.usdigital.com/assets/datasheets/datasheet-E6.pdf#page=7) · [E6 connector pinout](https://www.usdigital.com/assets/datasheets/datasheet-E6.pdf#page=9)

| E6 pin | Signal | Connection for the Gnoom sketch |
| --- | --- | --- |
| 1 | Ground | Arduino GND and supply ground |
| 2 | Index | Unused |
| 3 | Channel A | Arduino D2 |
| 4 | Supply | Regulated 5 V |
| 5 | Channel B | Arduino D7 |

The [Arduino sketch](../../arduino/rotary/rotary_only.ino) sends one byte on each rising and falling edge of A and samples B to determine direction. This ×2 decoding gives **5,000 steps per encoder shaft revolution**. With the wiring above, clockwise rotation as viewed from the encoder cover sends `0x01` and counterclockwise rotation sends `0x00`. Use **Invert Encoder** if forward travel on the apparatus moves the camera backward. [E6 phase relationship](https://www.usdigital.com/assets/datasheets/datasheet-E6.pdf#page=7)

## Set the virtual travel gain

Select `LinearTrackDomeCalibration`, the root node of `godot4/dome/linear_track_dome_calibration.tscn`, and set **Meters Per Step** in the Inspector. Gain is virtual travel divided by physical travel. A gain of `1.0` gives equal distances.

Use the effective circumference of the running surface if it is driven by a wheel, or measure its travel over a known number of turns. Include the drive ratio if the wheel and encoder turn at different speeds. The 12 mm bore is the shaft mounting dimension.

```text
steps_per_wheel_revolution = 5000 × encoder_revolutions_per_wheel_revolution
meters_per_step = gain × physical_travel_per_wheel_revolution_m / steps_per_wheel_revolution
```

The demo setting of `0.0001` m per step gives **0.50 m of virtual travel per encoder revolution**. With direct 1:1 drive, that is unity gain for a wheel with a 0.50 m effective circumference, about 159 mm in diameter.

## Verify the count on the apparatus

1. Run `GNOOM_SERIAL_DEBUG=1 ./run-godot.sh` from the repository root and wait for the encoder to connect. [Godot encoder setup](../../godot4/README.md#arduino-rotary-encoder)
2. Mark the encoder shaft and turn it one full revolution slowly in one direction. Wait for the last console report, then sum the `0x01` and `0x00` counts for that turn across all reports. Their absolute difference should be about 5,000. Repeat in the opposite direction to confirm the sign.
3. To calibrate directly from the assembled mechanism, repeat with a measured length of running-surface travel. Divide that length in meters by the absolute difference of the two counts, then multiply by the desired gain.

For an Arduino Uno with a USB-to-UART bridge, the nominal 115,200 baud, 8N1 link carries at most 11,520 step bytes per second. That corresponds to about **138 encoder RPM** at ×2. The sketch drops new steps when its queue fills, so repeat the measured-travel check at operating speed if it approaches that limit. [Arduino AVR serial defaults](https://github.com/arduino/ArduinoCore-avr/blob/master/cores/arduino/HardwareSerial.h)
