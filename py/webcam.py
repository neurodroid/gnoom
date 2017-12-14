# 2010-03-19
# C. Schmidt-Hieber, University College London


# Echo client program
import socket
import time
import sys
sys.path.append("/usr/local/lib/python2.6/site-packages")
import subprocess
import cv
import tempfile
import datetime

def get_image(camera, width, height, writer=None, s=None, rotate=True):
    im = cv.QueryFrame(camera)
    imrot = cv.CloneImage(im)
    if rotate:
        cv.WarpAffine(im, imrot, gMapping)
    if writer is not None:
        write_send(camera, imrot, writer, s)
    # im = Image.fromstring("RGB", cv.GetSize(im), im.tostring(), "raw", "BGR")
    return imrot

def write_send(camera, im, writer, s):
    try:
        # print "Sending %f " % time.time()
        s.send(('%f ' % time.time()).encode('latin-1'))
    except:
        pass
    cv.WriteFrame(writer, im)

if __name__ == "__main__":

    fps = 25.0
    target_dur = 1.0/fps

    camera = cv.CreateCameraCapture(0)
    width = cv.GetCaptureProperty(camera, cv.CV_CAP_PROP_FRAME_WIDTH)
    height = cv.GetCaptureProperty(camera, cv.CV_CAP_PROP_FRAME_HEIGHT)
    cv.SetCaptureProperty(camera, cv.CV_CAP_PROP_FRAME_WIDTH, 640)
    cv.SetCaptureProperty(camera, cv.CV_CAP_PROP_FRAME_HEIGHT, 480)
    width = 640
    height = 480
    print("WEBCAM: Initialized camera with", width, "x", height)
    global gMapping
    gMapping = cv.CreateMat(2, 3, cv.CV_32FC1)
    cv.GetRotationMatrix2D((width/2.0,height/2.0), 180.0, 1.0, gMapping)

    cv.NamedWindow("Webcam")
    cv.MoveWindow("Webcam", 1280, 0)
    im = get_image(camera, width, height)
    cv.ShowImage("Webcam", im)
    time.sleep(0.2)

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connected = False
    while not connected:
        try:
            s.connect("\0vidsocket")
            connected=True
        except:
            pass

    try:
        datapath = (s.recv(1024)).decode('latin-1')
        s.send(b'ready')
    except:
        pass

    s.setblocking(0)
    writer = None
    nframes = 0
    time0 = time.time()
    time1 = time0
    while True:
        time1 = time.time()
        # print "Precision:", (time1-time0) - nframes*target_dur, "ms",
        datadec = ""
        try:
            data = s.recv(1024)
            datadec = data.decode('latin-1')
            has_data = True
        except:
            has_data = False

        im = get_image(camera, width, height, writer, s)

        cv.ShowImage("Webcam", im)
        capture_dur = time.time()-time1
        rem = target_dur-capture_dur
        tol = 1.0*1e-3
        if rem > tol:
            nframes += 1
        else:
            # Drop frames until we're in sync again:
            dropped_frames = int((capture_dur+tol)/target_dur)
            # print "Dropped",  dropped_frames, "frames, ",
            nframes += dropped_frames+1
            for nf in range(dropped_frames):
                if writer is not None:
                    write_send(camera, im, writer, s)
            
        next_timestamp = (nframes * target_dur) + time0
        total_wait = next_timestamp - time.time()

        # cv.WaitKey will block with 0:
        while total_wait < tol:
            total_wait += target_dur
            nframes += 1
            if writer is not None:
                write_send(camera, im, writer, s)

        # print "will wait for", total_wait*1e3 , "ms to synchronize",
        key = cv.WaitKey(int(1000.0*total_wait))
        while key != -1:
            next_timestamp = (nframes * target_dur) + time0
            if time.time() < next_timestamp:
                total_wait = next_timestamp - time.time()
            else:
                break
            key = cv.WaitKey(int(1000.0*total_wait))

        if True:
            # No update from blender in a long time, terminate process
            if (has_data and datadec.find('1') == -1 and datadec.find('avi') == -1):# or (not has_data):
                if connected:
                    t_disconnect = time.time()
                connected = False
                if time.time()-t_disconnect > 0.1:
                    sys.stdout.write('WEBCAM: Received termination signal... ')
                    sys.stdout.flush()
                    break
            else:
                connected=True

            # Stop the recording
            if has_data and datadec.find('stop') != -1 and writer is not None:
                print("WEBCAM: Stopping video")
                del(writer)
                writer = None
                # cmd = ['a2mp4.sh', '%s' % fn, '%s.mp4' % fn[:-4]]
                # proc = subprocess.Popen(cmd, bufsize=-1)
            if has_data and datadec.find('avi') != -1 and datadec.find('stop') == -1:
                if writer is None:
                    print("WEBCAM: Starting video")
                    fn = datadec[datadec.find("begin")+5:datadec.find("end")]
                    writer = cv.CreateVideoWriter(fn, cv.CV_FOURCC('X','V','I','D'), fps, (width,height), True)
                connected=True

        # except:
        #     pass

        # print

    
    cv.DestroyWindow("Webcam")    
    s.close()
    sys.stdout.write("done\n")
    sys.exit(0)