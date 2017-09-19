# 2010-03-19
# C. Schmidt-Hieber, University College London


# Echo client program
import socket
import time
import sys
import os
import subprocess
import cv2
import openmv
import tempfile
import datetime
import numpy as np

script = """
import sensor, image, time

sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE) # grayscale is faster
sensor.set_framesize(sensor.VGA)   # Set frame size to QVGA (320x240)
sensor.set_windowing((260, 200, 120, 80))   # Set frame size to QVGA (320x240)
sensor.skip_frames(time = 100)

while(True):
    img = sensor.snapshot()
    sensor.flush()
"""

def write_send(im, writer, s):
    try:
        # print "Sending %f " % time.time()
        s.send(('%f ' % time.time()).encode('latin-1'))
    except:
        pass

    writer.write(im)


def init_socket(sockno):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connected = False
    while not connected:
        try:
            s.connect("\0vidsocket%d" % sockno)
            connected=True
        except:
            pass

    try:
        blenderpath = (s.recv(1024)).decode('latin-1')
        s.send(b'ready')
    except:
        blenderpath = None

    s.setblocking(0)

    return s, blenderpath, connected

    
if __name__ == "__main__":

    if len(sys.argv) > 1:
        sockno = int(sys.argv[1])
    else:
        sockno = 0
    s, datapath, connected = init_socket(sockno)

    if datapath is None:
        s.close()
        sys.stdout.write("OPENMV: ERROR: Could not connect to Blender, exiting now\n")
        sys.exit(0)

    # init openmv
    if 'darwin' in sys.platform:
        portnames = glob.glob("/dev/cu.usbmodem*")
        if len(portnames):
            portname = portnames[0]
        else:
            portname = None
    else:
        portname = "/dev/openmvcam"

    openmv.init(portname)
    openmv.stop_script()
    openmv.enable_fb(True)
    openmv.exec_script(script)

    # init OpenCV window
    win = cv2.namedWindow('OpenMV')
    cv2.moveWindow("OpenMV", 1280, 0)

    fb = None

        
    writer = None
    f_timestamps = None
    nframes = 0
    while True:
        datadec = ""
        try:
            data = s.recv(1024)
            datadec = data.decode('latin-1')
            has_data = True
        except:
            has_data = False

        fb = None
        while fb is None:
            key = cv2.waitKey(1)
            try:
                fb = openmv.fb_dump()
            except:
                pass
        if f_timestamps is not None:
            f_timestamps.write(np.array([time.time()]).tobytes())
            f_timestamps.flush()
        im = cv2.cvtColor(fb[2],cv2.COLOR_RGB2GRAY)
        if writer is not None:
            write_send(im, writer, s)

        cv2.imshow('OpenMV', im)

        if True:
            # No sensible update from blender in a long time, terminate process
            if (has_data and datadec.find('1') == -1 and datadec.find('avi') == -1) or (not has_data):
                if connected:
                    t_disconnect = time.time()
                connected = False
                if time.time()-t_disconnect > 1.0:
                    sys.stdout.write('OPENMV: timeout, exiting now... ')
                    sys.stdout.flush()
                    break
            else:
                connected=True

            if has_data and datadec.find('quit')!=-1:
                sys.stdout.write("OPENMV: Game over signal received\n")
                s.send(b'close')
                break
            
            # Stop the recording
            if has_data and datadec.find('stop') != -1 and writer is not None:
                print("OPENMV: Stopping video")
                writer.release()
                del(writer)
                writer = None
                f_timestamps.flush()
                f_timestamps.close()
                f_timestamps = None
                # cmd = ['a2mp4.sh', '%s' % fn, '%s.mp4' % fn[:-4]]
                # proc = subprocess.Popen(cmd, bufsize=-1)
            if has_data and datadec.find('avi') != -1 and datadec.find('stop') == -1:
                if writer is None:
                    fn = datadec[datadec.find("begin")+5:datadec.find("end")]
                    os.makedirs(fn)
                    fn_timestamps = fn + ".timestamps"
                    fn = os.path.join(fn, r'_%09d.jpg')
                    print("OPENMV: Starting video " + fn)
                    f_timestamps = open(fn_timestamps, 'wb')
                    # fourcc = cv2.VideoWriter_fourcc(*'FFV1')
                    writer = cv2.VideoWriter()
                    writer.open(fn, 0, 0, (160, 120))
                    assert(writer.isOpened())
                connected=True

        # except:
        #     pass

        # print

    
    openmv.stop_script()
    cv2.destroyAllWindows()
    s.close()
    sys.stdout.write("done\n")
    sys.exit(0)
