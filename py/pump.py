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

sys.stdout.write("Opening serial port...")
sys.stdout.flush()
ser = serial.Serial('/dev/ttyS0', 19200, bytesize=8, parity='N', stopbits=1, timeout=1)
# ser = serial.Serial('/dev/ttyUSB2', 19200, bytesize=8, parity='N', stopbits=1, timeout=None, xonxoff=0, rtscts=0)
sys.stdout.write(" done\n")

def write_bytes(string):
    ser.write(bytearray(string, 'ascii'))

def init():
    sys.stdout.write( "Resetting pump..." )
    sys.stdout.flush()
    write_bytes("*RESET\r\n")
    ser.read()
    sys.stdout.write( " done\n" )
    sys.stdout.write( "Setting syringe diameter..." )
    sys.stdout.flush()
    write_bytes("DIA 14.43\r\n") # B-D 10 ml
    ser.read()
    sys.stdout.write( " done\n" )
    sys.stdout.write( "Setting direction..." )
    sys.stdout.flush()
    write_bytes("DIR INF\r\n")
    ser.read()
    sys.stdout.write( " done\n" )
    sys.stdout.write( "Setting alarm..." )
    sys.stdout.flush()
    write_bytes("AL 0\r\n")
    ser.read()
    sys.stdout.write( " done\n" )
    set_rate(05.00)
    ser.read()
    # set_volume(10) # changed to 20 on 2012-01-17, CSH
    set_volume(20.0) 
    ser.read()

def set_volume(vol):
    svol = "%05.2f" % vol
    sys.stdout.write( "Setting volume to %s ul..." % svol )
    sys.stdout.flush()
    write_bytes("VOL UL\r\n")
    ser.read()
    write_bytes("VOL %s\r\n" % svol)
    ser.read()
    sys.stdout.write( " done\n" )

def set_rate(rate):
    srate = "%05.2f" % rate
    sys.stdout.write( "Setting rate to %s..." % srate ) 
    sys.stdout.flush()
    write_bytes("RAT %s MM\r\n" % srate)
    ser.read()
    sys.stdout.write( " done\n" )

def start_pump():
    write_bytes("RUN\r\n")
    ser.read()
    write_bytes("BUZ 1 2\r\n")
    ser.read()

def stop_pump():
    write_bytes("STP\r\n")
    ser.read()
    write_bytes("STP\r\n")
    ser.read()

if __name__=="__main__":
    init()
