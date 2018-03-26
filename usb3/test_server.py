import os
import sys
import socket
import subprocess
import time
import numpy as np

def recv_ready(conn, usezmq=False):
    datadec = ""
    start = time.time()
    while datadec != 'ready':
        try:
            if usezmq:
                data = conn.recv()
            else:
                data = conn.recv(1024)
            datadec = data.decode('latin-1')
        except:
            if time.time()-start > 3.0:
                return False
    return True


def spawn_process(procname, cmd='', shell=False, system=False, start=True, addenv=None, usezmq=False):
    if usezmq:
        s = settings.ZMQCONTEXT.socket(zmq.REP)
    else:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    screated = False
    ntry = 0
    sprocname = procname
    if addenv is not None:
        env = dict(os.environ)
        env.update(addenv)
    else:
        env=None
        
    while not screated:
        procname = sprocname + "%d" % ntry
        if usezmq:
            procname = procname.replace('\0', 'ipc://@')
        sys.stdout.write("BLENDER: Trying new socket name %s\n" % procname)
        ntry += 1
        try:
            s.bind(procname)
            screated = True
        except:
            pass

    cmd.extend([('%d' % (ntry-1)),])
    if start:
        if not system:
            proc = subprocess.Popen(cmd, shell=shell, bufsize=-1, env=env)
        else:
            print("BLENDER: Executing", cmd)
            proc = os.system(" ".join(cmd))
    else:
        proc=None
    if usezmq:
        conn, addr = s, None
    else:
        s.listen(1)
        conn, addr = s.accept()

    return s, conn, addr, proc

def disconnect(conn):
    if conn is None:
        return

    sent = False
    start = time.time()
    while not sent:
        try:
            conn.sendall(b"quit")
            sent=True
        except:
            if time.time()-start > 3.0:
                sys.stdout.write("BLENDER: Could not send quit signal, aborting now\n")
                break
    datadec = ""
    start = time.time()
    while datadec.find('close') == -1:
        try:
            dataraw = conn.recv(1024)
            datadec = dataraw.decode('latin-1')
            sys.stdout.flush()
        except:
            pass
        if time.time()-start > 3.0:
            sys.stdout.write("BLENDER: Could not close connection, aborting now\n")
            break
    conn.shutdown(socket.SHUT_RDWR)

def keep_conn(conn):
     try:
         if hasattr(conn, "send_string"):
             conn.send(b'1', flags=zmq.NOBLOCK)
         else:
             conn.send(b'1')
     except:
         sys.stdout.write(
             "BLENDER: Couldn't send signal, will retry...\n")

def parse_frametimes(conn):
    data1 = b''
    start = time.time()
    while True:
        try:
            data1 += conn.recv(8)
        except:
            break
        if time.time()-start > 3.0:
            sys.stdout.write("BLENDER: No frame times received, aborting now\n")
            return None
    if len(data1):
        datanp = np.fromstring(data1, np.float64)
    else:
        datanp = np.array([], dtype = np.float64)
    return datanp

def safe_send(conn, msg, errmsg, usezmq=False):
    sent = False
    start = time.time()
    while not sent:
        try:
            if usezmq:
                conn.send(msg.encode('latin-1'), flags=zmq.NOBLOCK)
            else:
                conn.send(msg.encode('latin-1'))
            sent = True
        except:
            sys.stdout.write(errmsg)
            sys.stdout.flush()
        if time.time()-start > 3.0:
            sys.stdout.write("BLENDER: safe_send failed, aborting now\n")
            return None


susb3, connusb3, addrusb3, pusb3 = \
    spawn_process("\0usb3socket", [os.path.abspath('./arv-camera-test'),],
                  system=False, addenv={"SDL_VIDEO_WINDOW_POS":"\"1280,480\""})

connusb3.send("/tmp/testmov".encode('latin-1'))
if not recv_ready(connusb3):
    sys.exit(1)
connusb3.setblocking(0)
t0 = time.time()
tcounter = time.time()-t0
break_all = False
safe_send(
    connusb3, "begin%send" % "tmp/testusb3.avi",
    "BLENDER: Couldn't start video; resource unavailable\n")
tstop = 6.0
while tcounter < tstop and not break_all:
    keep_conn(connusb3)
    tframe = parse_frametimes(connusb3)
    if tframe is None:
        break
    start = time.time()
    while not len(tframe):
        tframe = parse_frametimes(connusb3)
        if tframe is None:
            breakall = True
            break
    tcounter = time.time()-t0
safe_send(connusb3, 'stop', '')
# disconnect(connusb3)
