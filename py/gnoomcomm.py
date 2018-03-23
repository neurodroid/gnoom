"""Communication with processes, arduino, pump, valves, etc"""

import bge.logic as GameLogic
import time
import sys
import socket
import subprocess
import numpy as np
import settings
import gnoomutils as gu
import gnoomio as gio
if settings.usezmq:
    import zmq

def safe_send(conn, msg, errmsg, usezmq=False):
    sent = False
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

def safe_recv(conn, usezmq=False):
    recv = False
    while not recv:
        try:
            if usezmq:
                data = conn.recv(flags=zmq.NOBLOCK)
            else:
                data = conn.recv(4096)
            recv = True
        except:
            sys.stdout.write("BLENDER: Didn't receive signal, will retry...\n")

    sys.stdout.write("done")
    return data

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
            if time.time()-start > 5000:
                return False
    return True
    
def keep_conn(connlist):
    for connname in connlist:
        if connname in GameLogic.Object.keys():
            conn = GameLogic.Object[connname]
            if conn is not None:
                try:
                    if hasattr(conn, "send_string"):
                        conn.send(b'1', flags=zmq.NOBLOCK)
                    else:
                        conn.send(b'1')
                except:
                    sys.stdout.write(
                        "BLENDER: Couldn't send signal to {0}, will retry...\n".format(connname))

def read32(conn, usezmq=False):

    data1 = b''
    while True:
        try:
            if usezmq:
                data1 += conn.recv(flags=zmq.NOBLOCK)
            else:
                data1 += conn.recv(32)
        except:
            break
    if len(data1):
        datanp = np.fromstring(data1, np.float64)
        t = datanp[::4]
        dt = datanp[1::4]
        y = datanp[2::4]
        x = datanp[3::4]
    else:
        t, dt, x, y = np.array([time.time()]),np.array([0]),np.array([0]),np.array([0])

    return t,dt,x,y

def parse_frametimes(conn):
    data1 = b''
    while True:
        try:
            data1 += conn.recv(8)
        except:
            break
    if len(data1):
        datanp = np.fromstring(data1, np.float64)
    else:
        datanp = np.array([], dtype = np.float64)
    return datanp

def parse_ephystimes(conn):
    recv = False
    while not recv:
        try:
            data = conn.recv(8)
            recv = True
        except:
            pass
    return np.fromstring(data, np.float64)

def parse_licksensor(conn):
    data1 = b''
    while True:
        try:
            data1 += conn.recv(16)
        except:
            break
    if len(data1):
        datanp = np.fromstring(data1, np.float64)
        datanp = datanp.reshape((int(datanp.shape[0]/2), 2))
    else:
        datanp = np.array([], dtype = np.float64)
    return datanp

def parse_imgsensor(conn):
    data1 = b''
    while True:
        try:
            data1 += conn.recv(1)
        except:
            break
    if len(data1):
        datanp = np.fromstring(data1, np.int8)
        # datanp = datanp.reshape((int(datanp.shape[0]/2), 2))
    else:
        datanp = np.array([], dtype = np.float64)
    return datanp


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

def spawn_process_net(hostname):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.1)
    s.bind((hostname, 35000))
    s.listen(5)
    try:
        conn, addr = s.accept()
    except:
        conn, addr = None, None
    return s, conn, addr

def read_optical_sensor():
    if GameLogic.Object['m1conn'] is not None:
        # get mouse movement
        t1, dt1, x1, y1 = read32(GameLogic.Object['m1conn'], usezmq=settings.usezmq)
    else:
        t1, dt1, x1, y1 = np.array([0,]), np.array([0,]), np.array([0,]), np.array([0,])

    if GameLogic.Object['m2conn'] is not None:
        t2, dt2, x2, y2 = read32(GameLogic.Object['m2conn'], usezmq=settings.usezmq)
    else:
        t2, dt2, x2, y2 = np.array([0,]), np.array([0,]), np.array([0,]), np.array([0,])
        
    return x1, y1, x2, y2, t1, t2, dt1, dt2

def read_licksensor():
    licks = parse_licksensor(GameLogic.Object['lickconn'])
    if licks.shape[0] > 0:
        try:
            if np.any(licks[:,1]):
                gio.write_licks(licks)
        except:
            pass

def read_licksensor_piezo():
    licks = parse_licksensor(GameLogic.Object['lickpiezoconn'])
    if licks.shape[0] > 0:
        if np.any(licks[:, 1]):
            gio.write_licks_piezo(licks)
            GameLogic.Object['piezolicks'] += np.sum(licks[:, 1])
            GameLogic.Object['piezoframes'] += 1
        elif GameLogic.Object['piezoframepause'] < 10:
            GameLogic.Object['piezoframepause'] += 1
        else:
            # End of a lick period
            if GameLogic.Object['piezolicks'] != 0:
                sys.stdout.write('BLENDER: Lick period detected:\n')
                sys.stdout.write(
                    '         {0} amplitude, {1} frames\n'.format(
                    GameLogic.Object['piezolicks'], GameLogic.Object['piezoframes']))
            GameLogic.Object['piezolicks'] = 0
            GameLogic.Object['piezoframes'] = 0
            GameLogic.Object['piezoframepause'] = 0
            
            
def zeroPump():
    if not settings.looming:
        scene = GameLogic.getCurrentScene()
        if scene.name == "Scene":
            rew1Name = 'Cylinder.001'
        else:
            rew1Name = 'Cone.001'
        cyl = scene.objects[rew1Name]
        cyl.localPosition = [0, GameLogic.Object['rewpos'][0] * settings.reward_pos_linear, cyl.localPosition[2]]
    
def runPump(pumppy, reward=True, buzz=True):
    if pumppy is not None:
        try:
            if reward:
                sys.stdout.write("BLENDER: Running reward pump\n")
                pumppy.write(b"RUN\r")
            if buzz:
                pumppy.write(b"BUZ 1 2\r")
        except:
            sys.stdout.write('BLENDER: Pump not found\n')
                                                                                                           
def setPumpVolume(pumppy, vol):
    svol = "%05.2f" % vol
    sys.stdout.write( "BLENDER: Setting pump volume to %s ul...\n" % svol )
    pumppy.write(bytearray("VOL UL\r\n", 'ascii'))
    pumppy.write(bytearray("VOL %s\r\n" % svol, 'ascii'))



def open_valve(no, kb=None):
    
    if no == 0:
        cmd_list = [b'6', b'8', b'0']
    elif no == 1:
        cmd_list = [b'5', b'8', b'0']
    elif no == 2:
        cmd_list = [b'7', b'6', b'0']
    elif no == 3:
        cmd_list = [b'9', b'6', b'8']
    else:
        sys.stderr.write("GNOOMUTILS: Valve no %d doesn't exist\n" % no)
        return
           
    for cmd in cmd_list:
        valve_command(GameLogic.Object['arduino'], cmd, kb=kb)
        
def valve_command(arduino, cmd, kb=None):
    if arduino is None:
        return

    if kb is not None:
        run_code = kb.positive
    else:
        run_code = True
    if run_code:
        time1 = time.time()
        if GameLogic.Object['train_open']:
           dt = time1 -  GameLogic.Object['train_tstart']
        else:
           dt = time1 -  GameLogic.Object['time0']
        print("%ss " % (gu.time2str(dt))+ str(kb))
        executed = False
        while not executed:
            try:
                arduino.write(cmd)
                executed = True
                gio.write_valve(cmd)
            except BlockingIOError:
                sys.stderr.write("GNOOMUTILS: Couldn't write to arduino\n")

def write_arduino_nonblocking(arduino, cmd):
    while True:
        try:
            arduino.write(cmd)
            break
        except BlockingIOError:
            pass    

# convert 2 unsigned char to a signed int
def u2s(u, d):
    if d < 127:
        return d*256 + u
    else:
        return (d-255)*256 - 256 + u

def read_mouse(dev, timeout=3):
    # get mouse movement (legacy code)
    x, y = 0, 0
    try:
        readout = [ord(dat) for dat in dev.interruptRead(0x81,8, timeout)]
        y = u2s(readout[2], readout[3])
        x = u2s(readout[4], readout[5])
    except:
        pass

    return x, y


