#! /bin/bash
ARDUINOPATH=/home/cs/arduino-0022

./reset.pl
make
$ARDUINOPATH/hardware/tools/avrdude -V -F -C $ARDUINOPATH/hardware/tools/avrdude.conf -p atmega168 -P /dev/ttyUSB$1 -c stk500v1 -b 19200 -U flash:w:applet/flash.hex
./reset.pl
