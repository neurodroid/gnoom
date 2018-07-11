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

# Program a New Era Syringe Pump via the serial port
# (c) C. Schmidt-Hieber, 2013

import serial
import sys
import time
import socket

sys.stdout.write("Opening serial port...")
sys.stdout.flush()

if socket.gethostname() == 'dent3' or socket.gethostname() == 'dent4':
    socketrange = range(31, -1, -1)
else:
    socketrange = range(10)

if socket.gethostname() == 'dent3':
    socketbasename = '/dev/ttyUSB'
else:
    socketbasename = '/dev/ttyS'

for nport in socketrange:
    try:
        portname = '{0}{1:d}'.format(socketbasename, nport)
        ser = serial.Serial(portname, 19200, bytesize=8, parity='N', stopbits=1, timeout=None)
        print("Pump found on port " + portname)
        break
    except serial.serialutil.SerialException:
        nport += 1

# ser = serial.Serial('/dev/ttyACM0', 19200, bytesize=8, parity='N', stopbits=1, timeout=None)
time.sleep(2.0)
# ser = serial.Serial('/dev/ttyUSB2', 19200, bytesize=8, parity='N', stopbits=1, timeout=None, xonxoff=0, rtscts=0)
sys.stdout.write(" done\n")

def write_bytes(string, block=True):
    resp = '1'
    while resp != '0':
        ser.write(bytearray(string, 'ascii'))
        resp = ser.read().decode('utf-8')
        if not block:
            break
        time.sleep(0.5)
    print(resp)

def read_bytes():
    resp = ser.read()
    return " Response: " + str(resp) + " " + resp.decode('utf-8') + "\n"

def init():
    sys.stdout.write( "Resetting pump..." )
    sys.stdout.flush()
    write_bytes("*RESET\r\n")

    sys.stdout.write( "Setting syringe diameter..." )
    sys.stdout.flush()
    write_bytes("DIA 14.43\r\n") # B-D 10 ml

    sys.stdout.write( "Setting direction..." )
    sys.stdout.flush()
    write_bytes("DIR INF\r\n")

    sys.stdout.write( "Setting alarm..." )
    sys.stdout.flush()
    write_bytes("AL 0\r\n")

    sys.stdout.write( "Setting rate..." )
    sys.stdout.flush()
    set_rate(8.3)

    # set_volume(10) # changed to 20 on 2012-01-17, CSH
    sys.stdout.write( "Setting volume..." )
    sys.stdout.flush()
    set_volume(20.0)

def set_volume(vol):
    svol = "%05.2f" % vol
    sys.stdout.write( "Setting volume to %s ul..." % svol )
    sys.stdout.flush()
    write_bytes("VOL UL\r\n")
    write_bytes("VOL %s\r\n" % svol)

def set_rate(rate):
    srate = "%05.2f" % rate
    sys.stdout.write( "Setting rate to %s..." % srate ) 
    sys.stdout.flush()
    write_bytes("RAT %s MM\r\n" % srate)

def start_pump():
    write_bytes("RUN\r\n", False)
    write_bytes("BUZ 1 2\r\n", False)

def stop_pump():
    write_bytes("STP\r\n", False)
    write_bytes("STP\r\n", False)

if __name__=="__main__":
    init()
