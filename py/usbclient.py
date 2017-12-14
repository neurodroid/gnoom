# 2010-07-12, C. Schmidt-Hieber

# Echo client program
import socket
import usb1
import time
import sys
import numpy as np

def init(ind=0):
    # initialize usb mice
    iGIdVendor =  0x046d # Logitech
    iGIdProduct = 0xc068 # G500

    # find our device 
    ctx = usb1.LibUSBContext()
    alldevs = ctx.getDeviceList()
    devs = [dev for dev in alldevs if dev.getVendorID()==iGIdVendor and dev.getProductID()==iGIdProduct]
    devh = devs[ind].open()
    devh.claimInterface(0)
    return devh

# convert 2 unsigned char to a signed int
def u2s(u, d):
    if d < 127:
        return d*256 + u
    else:
        return (d-255)*256 - 256 + u

def read_mouse(dev, timeout=3):
    # get mouse movement
    x, y = 0, 0
    try:
        readout = [ord(dat) for dat in dev.interruptRead(0x81, 8, timeout)]
        y = u2s(readout[2], readout[3])
        x = u2s(readout[4], readout[5])
    except:
        pass

    return x, y

if __name__ == "__main__":
    # parse arguments:
    index = 0
    if len(sys.argv) > 1:
        if sys.argv[1] != '0':
            index = 1
    dev = init(index)

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connected = False
    bac_connection = False
    while not connected:
        try:
            s.connect("\0mouse%dsocket" % index)
            connected=True
        except:
            pass
    s.setblocking(0)
    time0 = time.time()
    while True:
        time1 = time.time()
        diff = (time1-time0)*1e3
        time0 = time.time()
        x,y = read_mouse(dev, timeout=2)
        try: 
            s.send(np.array([diff, x, y], dtype=np.float32).tostring(np.float32))
            bad_connection = False
        except:
            bad_connection = True
        datadec = ""
        try: 
            data = s.recv(1024)
            datadec = data.decode('latin-1')
            has_data = True
        except:
            has_data = False

        if has_data and datadec.find('1') == -1:
            if connected:
                t_disconnect = time.time()
            connected = False
            if time.time()-t_disconnect > 0.1:
                sys.stdout.write('USBCLIENT: Received termination signal... ')
                sys.stdout.flush()
                break
        else:
            connected = True

        if bad_connection:
            if connected:
                t_disconnect = time.time()
            connected = False
            if time.time()-t_disconnect > 0.1:
                sys.stdout.write('USBCLIENT: Abandoning connection... ')
                sys.stdout.flush()
                break
        else:
            connected = True
    sys.stdout.write("done\n")
    s.close()
    sys.exit(0)