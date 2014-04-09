# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# Read out optical lick sensor and broadcast data via socket
# (c) C. Schmidt-Hieber, 2013

import sys
import os
import socket
import time

import numpy as np

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../arduino/py")
import arduino_serial

def init_socket(sockno):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connected = False
    while not connected:
        try:
            s.connect("\0licksocket%d" % sockno)
            connected=True
        except:
            pass

    try:
        blenderpath = (s.recv(1024)).decode('latin-1')
        s.send(b'ready')
    except:
        pass

    s.setblocking(0)

    return s, blenderpath, connected

if __name__=="__main__":
    if len(sys.argv) > 1:
        sockno = int(sys.argv[1])
    else:
        sockno = 0

    socklick, blenderpath, connected = init_socket(sockno)

    try:
        arduino = arduino_serial.SerialPort("/dev/ttyUSB0", 19200)
        sys.stdout.write("LICKSENSOR: Successfully opened arduino\n")
    except OSError:
        sys.stdout.write("LICKSENSOR: Failed to open arduino\n")
        arduino = None

    datadec = ""

    time0 = time.time()
    while True:
        time1 = time.time()
        datadec = ""
        try:
            data = socklick.recv(1024)
            datadec = data.decode('latin-1')
            has_data = True
        except:
            has_data = False

        # No sensible update from blender in a long time, terminate process
        if (not has_data) or (has_data and datadec.find('1') == -1):
            if connected:
                t_disconnect = time.time()
            connected = False
            if time.time()-t_disconnect > 0.5:
                break
        else:
            connected=True
            
        # Explicit quit signal
        if has_data and datadec.find('quit')!=-1:
            sys.stdout.write("LICKSENSOR: Game over signal received\n")
            socklick.send(b'close')
            break
            
        if arduino is not None:
            arduino.write('w'.encode('latin1'))
            lickcounter = arduino.read_until(b'\n')
            int_lickcounter = np.fromstring(lickcounter[:-1], dtype=np.int8)
            if int_lickcounter.shape[0] == 0:
                int_lickcounter = [0]
        else:
            int_lickcounter = [0]
        try:
            socklick.send(np.array([time.time(), int_lickcounter[0]], dtype=np.float64).tostring()) 
        except BlockingIOError:
            pass

    socklick.close()
    sys.stdout.write("LICKSENSOR: Closing\n")
    sys.stdout.flush()
    sys.exit(0)
