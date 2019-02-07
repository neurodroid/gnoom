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

# Read out piezo lick sensor and broadcast data via socket
# (c) C. Schmidt-Hieber, 2013
import sys
import os
import socket
import time

import numpy as np

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../arduino/py")
import arduino_serial

TIMEOUT = 2.0

if 'linux' in sys.platform:
    arduino_port = None
    trunk = "/dev/ttyACM"
    for nport in range(0,9):
        arduino_port = "%s%i" % (trunk,nport)
        if os.path.exists(arduino_port):
            break
    if not os.path.exists(arduino_port):
        trunk = "/dev/ttyUSB"
        for nport in range(0,9):
            arduino_port = "%s%i" % (trunk,nport)
            if os.path.exists(arduino_port):
                break
else:
    arduino_port = "/dev/tty.usbserial-A6006klF"

def init_socket(sockno):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connected = False
    while not connected:
        try:
            s.connect("\0lickpiezosocket%d" % sockno)
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
        arduino = arduino_serial.SerialPort(arduino_port, 19200)
        sys.stdout.write("LICKPIEZOSENSOR: Successfully opened arduino\n")
    except OSError:
        sys.stdout.write("LICKPIEZOSENSOR: Failed to open arduino\n")
        arduino = None
 
    datadec = ""

    time0 = time.time()
    blocking = False
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
            if time.time()-t_disconnect > TIMEOUT:
                break
        else:
            connected=True
            
        # Explicit quit signal
        if has_data and datadec.find('quit')!=-1:
            sys.stdout.write("LICKPIEZOSENSOR: Game over signal received\n")
            socklick.send(b'close')
            break
            
        if arduino is not None:
            try:
                arduino.write('a'.encode('latin1'))
                if blocking:
                    sys.stderr.write("LICKPIEZOSENSOR: arduino unblocked\n")
                    blocking = False
                lickcounter = arduino.read_until(b'\n')
                int_lickcounter = np.fromstring(lickcounter[:-1], dtype=np.uint8)
                if int_lickcounter.shape[0] == 1:
                    int_lickcounter = [int_lickcounter[0]]
                elif int_lickcounter.shape[0] > 2:
                    sys.stderr.write("LICKPIEZOSENSOR: Warning: {0}\n".format(int_lickcounter))
                elif int_lickcounter.shape[0] != 0:
                    int_lickcounter = [int_lickcounter[0]*256 + int_lickcounter[1]]
                else:
                    int_lickcounter = [0]
            except BlockingIOError:
                sys.stderr.write("LICKPIEZOSENSOR: Couldn't write to arduino\n")
                blocking = True
                int_lickcounter = [0]
        else:
            int_lickcounter = [0]
        try:
            socklick.send(np.array([time.time(), int_lickcounter[0]], dtype=np.float64).tostring()) 
        except BlockingIOError:
            pass
        except BrokenPipeError:
            sys.stderr.write("LICKPIEZOSENSOR: Broken pipe\n")
            

    socklick.close()
    sys.stdout.write("LICKPIEZOSENSOR: Closing\n")
    sys.stdout.flush()
    sys.exit(0)
