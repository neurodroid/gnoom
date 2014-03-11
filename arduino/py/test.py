import sys
import arduino_serial
import time
import numpy as np

try:
    arduino = arduino_serial.SerialPort("/dev/ttyUSB0", 19200)
    sys.stdout.write("BLENDER: Successfully opened arduino\n")
except OSError:
    sys.stdout.write("BLENDER: Failed to open arduino\n")
    arduino = None

while True:
    arduino.write('w'.encode('latin1'))
    lickcounter = arduino.read_until(b'\n')
    int_lickcounter = np.fromstring(lickcounter[:-1], dtype=np.int8)
    print(int_lickcounter[0])
    time.sleep(0.5)
