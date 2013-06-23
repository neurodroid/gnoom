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
ser = serial.Serial('/dev/ttyS0', 19200, timeout=1)
# ser = serial.Serial('/dev/ttyUSB0', 19200, timeout=1)
sys.stdout.write(" done\n")

def init():
    sys.stdout.write( "Resetting pump..." )
    sys.stdout.flush()
    ser.write(b"*RESET\r")
    sys.stdout.write( " done\n" )
    sys.stdout.write( "Setting syringe diameter..." )
    sys.stdout.flush()
    ser.write(b"DIA 14.43\r") # B-D 10 ml
    ser.read()
    sys.stdout.write( " done\n" )
    sys.stdout.write( "Setting direction..." )
    sys.stdout.flush()
    ser.write(b"DIR INF\r")
    ser.read()
    sys.stdout.write( " done\n" )
    sys.stdout.write( "Setting alarm..." )
    sys.stdout.flush()
    ser.write(b"AL 0\r")
    ser.read()
    sys.stdout.write( " done\n" )
    set_rate(99)
    # set_volume(10) # changed to 20 on 2012-01-17, CSH
    set_volume(20) 

def set_volume(vol):
    svol = "%05.2f" % vol
    sys.stdout.write( "Setting volume to %s ul..." % svol )
    sys.stdout.flush()
    ser.write(b"VOL UL\r")
    ser.read()
    ser.write(b"VOL %s\r" % svol)
    sys.stdout.write( " done\n" )

def set_rate(rate):
    srate = "%05.2f" % rate
    sys.stdout.write( "Setting rate to %s..." % srate ) 
    sys.stdout.flush()
    ser.write(b"RAT %s\r" % srate)
    ser.read()
    sys.stdout.write( " done\n" )

def start_pump():
    ser.write(b"RUN\r")
    ser.write(b"BUZ 1 2\r")
    ser.read()

def stop_pump():
    ser.write(b"STP\r")
    ser.read()
    ser.write(b"STP\r")
    ser.read()

if __name__=="__main__":
    init()
