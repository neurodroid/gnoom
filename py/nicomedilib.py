# C. Schmidt-Hieber, University College London
# 2011-03-21

import os
import sys
import time
import string
import socket
import subprocess
import select
import settings

import numpy as np

try:
    import comedi as c
    has_comedi = True
    aref_ground = c.AREF_GROUND
    import stfio
except:
    sys.stderr.write("NICOMEDI: Failed to import comedi\n")
    has_comedi = False
    aref_ground = None

gPlot = True

def safe_send(conn, msg, errmsg):
    sent = False
    while not sent:
        try:
            conn.send(msg.encode('latin-1'))
            sent = True
        except:
            sys.stdout.write(errmsg)
            sys.stdout.flush()

def comedi_errcheck():
    errc = c.comedi_errno()
    raise Exception("NICOMEDI: %s" % c.comedi_strerror(errc))

def open_dev(devname):
    #open a comedi device
    sys.stdout.write("NICOMEDI: Opening comedi subdevice... ")
    sys.stdout.flush()

    dev=c.comedi_open(devname)
    name = c.comedi_get_board_name(dev)
    if not dev:
        comedi_errcheck()
    sys.stdout.write("found %s\n" % (name))
    sys.stdout.flush()

    #get a file-descriptor for use later
    fd = c.comedi_fileno(dev)
    if fd == -1:
        comedi_errcheck()

    return dev, fd, name

def make_cmd(subdev, dt, chlist, nchans):
    dt_ns = int(1.0e6*dt)

    cmd = c.comedi_cmd_struct()

    cmd.subdev = subdev
    cmd.flags = 0 # c.TRIG_WAKE_EOS

    cmd.start_src = c.TRIG_EXT
    cmd.start_arg = 0

    cmd.scan_begin_src = c.TRIG_TIMER
    cmd.scan_begin_arg =  dt_ns # ns

    cmd.convert_src = c.TRIG_TIMER
    cmd.convert_arg = 800 #dt_ns/nchans

    cmd.scan_end_src = c.TRIG_COUNT
    cmd.scan_end_arg = nchans

    cmd.stop_src = c.TRIG_NONE # continuous acquisition
    cmd.stop_arg = 0

    cmd.chanlist = chlist
    cmd.chanlist_len = nchans
    return cmd

def make_chlist(chans):
    # list containing the chans, gains and referencing
    nchans = len(chans) #number of channels

    #wrappers include a "chanlist" object (just an Unsigned Int array) for holding the chanlist information
    mylist = c.chanlist(nchans) #create a chanlist of length nchans

    #now pack the channel, gain and reference information into the chanlist object
    #N.B. the CR_PACK and other comedi macros are now python functions
    for index in range(nchans):
        mylist[index]=c.cr_pack(chans[index].no, chans[index].devrange, chans[index].aref)

    return mylist

class nichannel(object):
    def __init__(self, dev, no, subdev, fd, devrange, aref=aref_ground, 
                 calibrate=False, configpath=None, maxbuffer=131072):
        self.no = no
        self.dev = dev
        self.subdev = subdev
        self.fd = fd
        self.devrange = devrange
        self.aref = aref
        if calibrate:
            sys.stdout.write("NICOMEDI: Parsing calibration file... ")
            sys.stdout.flush()

            calib = c.comedi_parse_calibration_file(configpath)

            if calib is None or calib==0:
                sys.stdout.write("FAIL\n")
            else:
                self.convpoly = c.comedi_polynomial_t()
                conv = c.comedi_get_softcal_converter( \
                    self.subdev, self.no, self.devrange, c.COMEDI_TO_PHYSICAL,
                    calib, self.convpoly)
                c.comedi_cleanup_calibration(calib)
                if conv < 0:
                    sys.stdout.write("FAIL\n")
                else:
                    sys.stdout.write("success\n")
            sys.stdout.flush()
        else:
            self.convpoly = None
        self.maxdata = c.comedi_get_maxdata(self.dev, self.subdev, self.no)
        if self.maxdata == 0:
            comedi_errcheck()
        self.prange = c.comedi_get_range(self.dev, self.subdev, self.no, self.devrange)
        if self.prange == 0 or self.prange is None:
            comedi_errcheck()
        self.maxbuffer = c.comedi_get_max_buffer_size(self.dev, self.subdev)
        if self.maxbuffer == -1:
            comedi_errcheck()
        self.buffer = c.comedi_get_buffer_size(self.dev, self.subdev)
        sys.stdout.write("NICOMEDI: Buffer size: %d\n" % self.buffer)
        sys.stdout.flush()

def databstr2np(databstr, gains, channels):
    str2np = np.fromstring(databstr, np.uint32)
    if len(channels)==1:
        return np.array([c.comedi_to_physical(int(pt), channels[0].convpoly) \
                             for pt in str2np],
                        dtype=np.float32)/gains[0]
    else:
        arr1 = np.array([c.comedi_to_physical(int(pt), channels[0].convpoly) \
                             for pt in str2np[::3]],
                        dtype=np.float32)/gains[0]
        arr2 = np.array([c.comedi_to_physical(int(pt), channels[1].convpoly) \
                             for pt in str2np[1::3]],
                        dtype=np.float32)/gains[1]
        frames = np.array([int(c.comedi_to_physical(int(pt), channels[2].convpoly) > 2.5)\
                             for pt in str2np[2::3]],
                          dtype=np.int8)
        return arr1, arr2, frames

def find_edges(frames):
    return np.where(np.diff(frames)!=0)[0]

def init_comedi_ai(aichFR, aichIC, aichEC, dt):

    sys.stdout.write("NICOMEDI: Initializing analog inputs... ")
    sys.stdout.flush()

    chansai = [aichIC, aichEC, aichFR]
    chlistai = make_chlist(chansai)

    cmdai = make_cmd(aichIC.subdev, dt, chlistai, len(chansai))
    #test our comedi command a few times. 
    ntry = 0
    while c.comedi_command_test(aichIC.dev,cmdai):
        ntry += 1
        if ntry>10:
            raise Exception("NICOMEDI: Couldn't read from comedi AI device")

    sys.stdout.write("done\n")
    sys.stdout.flush()

    return cmdai

def set_dig_io(ch, mode):
    if mode=='out':
        io = c.COMEDI_OUTPUT
    else:
        io = c.COMEDI_INPUT

    ret = c.comedi_dio_config(ch.dev, ch.subdev, ch.no, io)
    if ret == -1:
        comedi_errcheck()

def init_comedi_dig(intrigch, outtrigch, outfrch, outleftch, outrightch, outexpch):

    sys.stdout.write("NICOMEDI: Initializing triggers... ")
    sys.stdout.flush()

    set_dig_io(intrigch, 'in')
    set_dig_io(outtrigch, 'out')
    set_dig_io(outfrch, 'out')
    set_dig_io(outleftch, 'out')
    set_dig_io(outrightch, 'out')
    set_dig_io(outexpch, 'out')

    set_trig(outtrigch, 0)
    set_trig(outfrch, 0)
    set_trig(outleftch, 0)
    set_trig(outrightch, 0)
    set_trig(outexpch, 0)

    sys.stdout.write("done\n")
    sys.stdout.flush()

def spawn_process(procname, cmd=['',], shell=False, system=False, start=True, ntry=None):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    screated = False
    sprocname = procname
    if ntry is None:
        ntry = 0
    else:   
        procname = sprocname + "%d" % ntry
        sys.stdout.write("BLENDER: Trying new socket name %s\n" % procname)
        ntry += 1
        s.bind(procname)
        screated = True
    while not screated:
        procname = procname + "%d" % ntry
        sys.stdout.write("BLENDER: Trying new socket name %s\n" % procname)
        ntry += 1
        try:
            s.bind(procname)
            screated = True
        except:
            pass

    if start:
        cmd.extend([('%d' % (ntry-1)),])
        if not system:
            proc = subprocess.Popen(cmd, shell=shell, bufsize=-1)
        else:
            print("BLENDER: Executing", cmd)
            proc = os.system(*cmd)
    else:
        proc=None
    s.listen(1)
    conn, addr = s.accept()
    return s, conn, addr, proc, ntry-1

def init_socket(sockno):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connected = False
    while not connected:
        try:
            s.connect("\0comedisocket%d" % sockno)
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

def disconnect(conn):
    sys.stdout.write('NICOMEDI: Received termination signal... ')
    sys.stdout.flush()
    sent = False
    while not sent:
        try:
            conn.sendall(b"quit")
            sent=True
        except:
            pass
    datawx = ""
    while datawx.find('close') == -1:
        try:
            datawxraw = conn.recv(1024)
            datawx = datawxraw.decode('latin-1')
            sys.stdout.write('received %s from wxplot... ' % datawx)
            sys.stdout.flush()
        except:
            pass                        
    sys.stdout.write('nicomedi done\n')

def record(aich, cmd, s=None):
    #execute the command!
    sys.stdout.write("NICOMEDI: Recording\n")
    sys.stdout.flush()
    ret = c.comedi_command(aich.dev, cmd)
    if ret != 0:
        comedi_errcheck()

def stop(aichIC, aichEC, aichFR, dt, xunits, yunitsIC, yunitsEC, gainIC, gainEC,
         fn, ftmpIC, fntmpIC, ftmpEC, fntmpEC, ftmpFR, fntmpFR, entmp, s,
         connic, connec, connfr, plot_sample, databstr_old):

    # Close device:
    ret = c.comedi_cancel(aichIC.dev, aichIC.subdev)
    # time stamp for last sample
    s.send(np.array([time.time(),], dtype=np.float64).tostring()) 
    if ret != 0:
        comedi_errcheck()

    # Empty buffer:
    # ret = c.comedi_poll(aich.dev, aich.subdev)
    # if ret < 0:
    #     comedi_errcheck()
    read_buffer(aichIC, aichEC, aichFR, gainIC, gainEC, connic, connec, connfr, plot_sample,
                ftmpIC, ftmpEC, ftmpFR, databstr_old)
    ftmpIC.close()
    ftmpEC.close()
    ftmpFR.close()

    # Scale temporary file:
    sys.stdout.write("NICOMEDI: Saving to file: Reading temp file...\n")
    sys.stdout.flush()
    ftmpIC = open(fntmpIC, 'rb')
    ftmpEC = open(fntmpEC, 'rb')
    ftmpFR = open(fntmpFR, 'rb')
    databstrIC = ftmpIC.read()
    databstrEC = ftmpEC.read()
    databstrFR = ftmpFR.read()
    sys.stdout.write("NICOMEDI: Saving to file: Processing data...\n")
    sys.stdout.flush()
    datalistIC = np.fromstring(databstrIC, np.float32)
    datalistEC = np.fromstring(databstrEC, np.float32)
    frames = np.fromstring(databstrFR, np.int8)
    # Write to hdf5:
    sys.stdout.write("NICOMEDI: Saving to file: Converting to hdf5...\n")
    sys.stdout.flush()
    chlist = [stfio.Channel([stfio.Section(np.array(datalistIC, dtype=np.float)),]),
              stfio.Channel([stfio.Section(np.array(datalistEC, dtype=np.float)),])]
    chlist[0].yunits = yunitsIC
    chlist[1].yunits = yunitsEC
    rec = stfio.Recording(chlist)
    rec.dt = dt # set sampling interval
    rec.xunits = xunits # set time units
    sys.stdout.write("NICOMEDI: Saving to file: Writing hdf5 to %s..." % fn)
    sys.stdout.flush()
    if sys.version_info >= (3,):
        rec.write(fn)
    else:
        rec.write(fn.encode('latin-1'))
    sys.stdout.write("done\n")
    sys.stdout.flush()

    # Write frame transition times
    if frames[0] != 0:
        sys.stdout.write("NICOMEDI: Warning: first frame isn't 0\n")
    edges = find_edges(frames)
    etmp = open(entmp, 'wb')
    etmp.write(edges.astype(np.int32).tostring())
    etmp.close()

    # Close and delete temp file:
    ftmpIC.close()
    ftmpEC.close()
    ftmpFR.close()
    # Do not remove temp files, CSH 2013-10-11
    # os.remove(fntmpIC)
    # os.remove(fntmpEC)
    # os.remove(fntmpFR)
    sys.stdout.write("\nNICOMEDI: Stopping acquisition, read %d samples\n" \
	                 % len(datalistIC))
    sys.stdout.flush()
    
    sys.stdout.write("NICOMEDI: Synchronizing in background\n")
    locald = os.path.dirname(fn)
    netd = os.path.dirname(locald.replace(settings.local_data_dir, settings.net_data_dir_mnt)) + '/'
    if not os.path.exists(netd):
        args = ["/usr/local/bin/sync_rackstation.sh"]
    else:
        netd = os.path.dirname(locald.replace(settings.local_data_dir, settings.net_data_dir)) + """/'"""
        args = ["/usr/bin/rsync", "-a", locald, netd]
    subprocess.Popen(args)
    
def rescue1ch(filetrnk, xunits="ms", yunits="mV", dt=0.02):
    sys.stdout.write("NICOMEDI: Rescuing file: Reading temp files...\n")
    sys.stdout.flush()

    fntmp = filetrnk + "_tmp.bin"
    fntmp2 = filetrnk + "_tmp2.bin"
    entmp = filetrnk + "_edge.bin"
    fn = filetrnk + ".h5"

    ftmp = open(fntmp, 'rb')
    ftmp2 = open(fntmp2, 'rb')
    databstr = ftmp.read()
    databstr2 = ftmp2.read()
    sys.stdout.write("NICOMEDI: Saving to file: Processing data...\n")
    sys.stdout.flush()
    datalist = np.fromstring(databstr, np.float32)
    frames = np.fromstring(databstr2, np.int8)
    # Write to hdf5:
    sys.stdout.write("NICOMEDI: Saving to file: Converting to hdf5...\n")
    sys.stdout.flush()
    chlist = [stfio.Channel([stfio.Section(np.array(datalist, dtype=np.float)),]),]
    chlist[0].yunits = yunits
    rec = stfio.Recording(chlist)
    rec.dt = dt # set sampling interval
    rec.xunits = xunits # set time units
    sys.stdout.write("NICOMEDI: Saving to file: Writing hdf5...")
    sys.stdout.flush()
    rec.write(fn)
    sys.stdout.write("done\n")
    sys.stdout.flush()

    # Write frame transition times
    if frames[0] != 0:
        sys.stdout.write("NICOMEDI: Warning: first frame isn't 0\n")
    edges = find_edges(frames)
    etmp = open(entmp, 'wb')
    etmp.write(edges.astype(np.int32).tostring())
    etmp.close()

    # Close and delete temp file:
    ftmp.close()
    ftmp2.close()
    os.remove(fntmp)
    os.remove(fntmp2)
    sys.stdout.write("\nNICOMEDI: Stopping acquisition, read %d samples\n" \
	                 % len(datalist))
    sys.stdout.flush()

def rescue2ch(filetrnk, xunits="ms", yunitsIC="mV", yunitsEC="mV", dt=0.02):
    sys.stdout.write("NICOMEDI: Rescuing file: Reading temp files...\n")
    sys.stdout.flush()
    
    fntmpIC = filetrnk + "_IC.bin"
    fntmpEC = filetrnk + "_EC.bin"
    fntmpFR = filetrnk + "_FR.bin"
    entmp =   filetrnk + "_edge.bin"
    fn =      filetrnk + ".h5"

    ftmpIC = open(fntmpIC, 'rb')
    ftmpEC = open(fntmpEC, 'rb')
    ftmpFR = open(fntmpFR, 'rb')

    databstrIC = ftmpIC.read()
    databstrEC = ftmpEC.read()
    databstrFR = ftmpFR.read()

    sys.stdout.write("NICOMEDI: Saving to file: Processing data...\n")
    sys.stdout.flush()
    datalistIC = np.fromstring(databstrIC, np.float32)
    datalistEC = np.fromstring(databstrEC, np.float32)
    frames = np.fromstring(databstrFR, np.int8)
    # Write to hdf5:
    sys.stdout.write("NICOMEDI: Saving to file: Converting to hdf5...\n")
    sys.stdout.flush()
    chlist = [stfio.Channel([stfio.Section(np.array(datalistIC, dtype=np.float)),]),
              stfio.Channel([stfio.Section(np.array(datalistEC, dtype=np.float)),])]
    chlist[0].yunits = yunitsIC
    chlist[1].yunits = yunitsEC
    rec = stfio.Recording(chlist)
    rec.dt = dt # set sampling interval
    rec.xunits = xunits # set time units
    sys.stdout.write("NICOMEDI: Saving to file: Writing hdf5...")
    sys.stdout.flush()
    rec.write(fn)
    sys.stdout.write("done\n")
    sys.stdout.flush()

    # Write frame transition times
    if frames[0] != 0:
        sys.stdout.write("NICOMEDI: Warning: first frame isn't 0\n")
    edges = find_edges(frames)
    etmp = open(entmp, 'wb')
    etmp.write(edges.astype(np.int32).tostring())
    etmp.close()

    # Close and delete temp file:
    ftmpIC.close()
    ftmpEC.close()
    ftmpFR.close()
    os.remove(fntmpIC)
    os.remove(fntmpEC)
    os.remove(fntmpFR)
    sys.stdout.write("\nNICOMEDI: Stopping acquisition, read %d samples\n" \
	                 % len(datalistIC))
    sys.stdout.flush()

def rescue_framesonly(filetrnk):
    sys.stdout.write("NICOMEDI: Rescuing file: Reading temp files...\n")
    sys.stdout.flush()

    fntmp2 = filetrnk + "_tmp2.bin"
    entmp = filetrnk + "_edge.bin"

    ftmp2 = open(fntmp2, 'rb')
    databstr2 = ftmp2.read()

    sys.stdout.write("NICOMEDI: Saving to file: Processing data...\n")
    sys.stdout.flush()
    frames = np.fromstring(databstr2, np.int8)

    # Write frame transition times
    if frames[0] != 0:
        sys.stdout.write("NICOMEDI: Warning: first frame isn't 0\n")
    edges = find_edges(frames)
    etmp = open(entmp, 'wb')
    etmp.write(edges.astype(np.int32).tostring())
    etmp.close()

    # Close and delete temp file:
    ftmp2.close()
    os.remove(fntmp2)

def read_buffer(aichIC, aichEC, aichFR, gainIC, gainEC, connic, connec, connfr, plot_sample,
                ftmpIC, ftmpEC, ftmpFR, databstr_old=b''):

    buffersize = c.comedi_get_buffer_contents(aichIC.dev, aichIC.subdev)
    if buffersize < 0:
        sys.stdout.write("NICOMEDI: Warning: buffer error\n")
        comedi_errcheck()
    if buffersize > aichIC.maxbuffer/2:
        sys.stdout.write("NICOMEDI: Warning: buffer is more than half full\n")
    
    if buffersize >= 12288:
        try:
            databstr_full = os.read(aichIC.fd, aichIC.maxbuffer)
        except:
            sys.stdout.write("NICOMEDI: Reading from device failed\n")
            sys.stdout.flush()
            databstr_full = b''

        databstr_full = databstr_old + databstr_full
        buffer12 = int(len(databstr_full)/12) * 12
        databstr = databstr_full[:buffer12]
        databstr_rem = databstr_full[buffer12:]

        tmpIC, tmpEC, frames = databstr2np(databstr, [gainIC, gainEC], [aichIC, aichEC, aichFR])
        ftmpIC.write(tmpIC.tostring()) 
        ftmpIC.flush()
        ftmpEC.write(tmpEC.tostring()) 
        ftmpEC.flush()
        ftmpFR.write(frames.tostring())
        ftmpFR.flush()
        if gPlot:
            try:
                connic.send(tmpIC[::plot_sample].tostring())
                connec.send(tmpEC[::plot_sample].tostring())
                connfr.send(frames[::plot_sample].tostring())
            except:
                sys.stdout.write("NICOMEDI: Error communicating with scope\n")
        sys.stdout.write('.')
        sys.stdout.flush()
        return databstr_rem

    else:
        time.sleep(1e-4)
        return databstr_old

def shutdown(aich):
    ret = c.comedi_close(aich.dev)
    if ret != 0:
        comedi_errcheck()

def set_trig(ch, state):
    ret = c.comedi_dio_write(ch.dev, ch.subdev, ch.no, state)
    if ret != 1:
        sys.stderr.write("NICOMEDI: Couldn't send trigger signal\n")
        comedi_errcheck()