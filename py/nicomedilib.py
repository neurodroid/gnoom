# C. Schmidt-Hieber, University College London
# 2011-03-21

import os
import sys
import time
import string
import socket
import subprocess
import select
import struct
import settings
import ctypes

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
READBUFFER = 12
MINBUFFER = 0

def safe_send(conn, msg, errmsg):
    while True:
        try:
            conn.send(msg.encode('latin-1'))
            break
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

def make_cmd_ao(subdev, dt, chlist, nchans, nsamples):
    dt_ns = int(1.0e6*dt)

    cmd = c.comedi_cmd_struct()

    cmd.subdev = subdev
    cmd.flags = 0 # c.TRIG_WAKE_EOS

    cmd.start_src = c.TRIG_INT
    cmd.start_arg = 0

    cmd.scan_begin_src = c.TRIG_TIMER
    cmd.scan_begin_arg =  dt_ns # ns

    cmd.convert_src = c.TRIG_NOW
    cmd.convert_arg = 0 #dt_ns/nchans

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
            self.convpoly_order = int(self.convpoly.order.real)
            self.convpoly_expansion_origin = self.convpoly.expansion_origin.real
            c_coeff = ctypes.c_double * (int(self.convpoly.order.real)+1)
            c_coeff = c_coeff.from_address(int(self.convpoly.coefficients))
            self.convpoly_coefficients = np.array([
                coeff.real for coeff in c_coeff])
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

def intn_trig(aochAO):
    '''
    Sets the internal trigger on the NI/comedi device.
    
    Keyword arguments:
    subd -- the integer subdevice number
    
    Supplies an internal trigger to the subdevice number
    given by the function argument. Returns a 1 if successful
    and a -1 if it fails.
    
    '''
    insn = c.comedi_insn_struct()
    insn.insn = c.INSN_INTTRIG
    insn.subdev = aochAO.subdev
    insn.n = 1
    data = c.lsampl_array(insn.n)
    data[0] = 0
    insn.data = data.cast()
    return c.comedi_do_insn(aochAO.dev, insn)


def byte_convert(waveform):
    '''
    From http://possm.googlecode.com/svn/trunk/controller/comediInterface.py
    Converts a waveform to a string of 2-byte numbers.

    Keyword arguments:
    waveform -- the waveform in list format

    byte_convert takes a list of integers (range 0-65535) and returns
    a string of 2-byte numbers. The string returned is the correct format
    for writing to the comedi data buffer for DAC operations.
    '''
    data = []
    for i in range(len(waveform)):
        data.append(struct.pack('H',waveform[i]))
    return b''.join(data)

def cpoly(data, channel):
    """
    The conversion algorithm is::
        x = sum_i c_i * (d-d_o)^i
    where `x` is the returned physical value, `d` is the supplied data,
    `c_i` is the `i`\th coefficient, and `d_o` is the expansion origin.
    i runs from 0 to order (inclusive).
    """
    return np.sum([channel.convpoly_coefficients[i] * (
                       data-channel.convpoly_expansion_origin)**i
                   for i in range(channel.convpoly_order+1)], axis=0)
       
def databstr2np(databstr, gains, channels):
    str2np = np.fromstring(databstr, np.uint32)
    if len(channels)==1:
        return np.array([c.comedi_to_physical(int(pt), channels[0].convpoly) \
                             for pt in str2np],
                        dtype=np.float32)/gains[0]
    else:
        arr1 = cpoly(str2np[0::3], channels[0]).astype(np.float32)/gains[0]
        arr2 = cpoly(str2np[1::3], channels[1]).astype(np.float32)/gains[1]
        arr3 = cpoly(str2np[2::3], channels[2]).astype(np.int)
        frames = (arr3 > 2.5).astype(np.int8)
#        arr1 = np.array([
#            c.comedi_to_physical(int(pt), channels[0].convpoly)
#            for pt in str2np[::3]], dtype=np.float32)/gains[0]
#        arr2 = np.array([
#            c.comedi_to_physical(int(pt), channels[1].convpoly)
#            for pt in str2np[1::3]], dtype=np.float32)/gains[1]
#        frames2 = np.array([
#            int(c.comedi_to_physical(int(pt), channels[2].convpoly) > 2.5)
#            for pt in str2np[2::3]], dtype=np.int8)
#        print("SUM", np.sum(frames2-frames), "SUM")
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

def init_comedi_ao(aochAO, dt, nsamples):

    sys.stdout.write("NICOMEDI: Initializing analog outputs... ")
    sys.stdout.flush()

    chansao = [aochAO]
    chlistao = make_chlist(chansao)

    cmdao = make_cmd_ao(aochAO.subdev, dt, chlistao, len(chansao), nsamples)
    #test our comedi command a few times. 
    ntry = 0
    while c.comedi_command_test(aochAO.dev, cmdao):
        ntry += 1
        if ntry>10:
            raise Exception("NICOMEDI: Couldn't write to comedi AO device")

    sys.stdout.write("done\n")
    sys.stdout.flush()

    return cmdao, chlistao

def scale_ao_700b_cc(current):
    gain_amp = 400.0 # pA/V
    # e.g. 100 pA -> 0.25 V
    voltage = current / gain_amp
    
    gain_digitizer = 20.0/65536.0 # V/16-bit input
    # e.g. 0.25 V -> 819.2
    input16 = int(np.round(voltage / gain_digitizer))
    
    return input16

def write_comedi_ao(aochAO, cmdao, waveform, chunksize=1024):
    data = byte_convert(waveform) # waveform.tobytes()
    err = c.comedi_command(aochAO.dev, cmdao)
    if err < 0:
       comedi_errcheck()

    m = os.write(aochAO.fd, data[:])
    print("Writing", m, "of", len(waveform), "bytes")
    if m == 0:
        raise Exception('NICOMEDI: write error')
    
    ret = 0
    while ret == 0:
        ret = intn_trig(aochAO)
    print('NICOMEDI: Internal trigger')
    if m < len(data):
        n=m
        while True:
            if n < len(data):
                written = False
                while not written:
                    try:
                        m = os.write(aochAO.fd, data[n:])
                        written = True
                    except BrokenPipeError:
                        pass
                print("Writing ", m, " bytes")
                n += m
                if m < 0:
                    raise Exception('NICOMEDI: write error')
                if m == 0:
                    break
            else: m = 0
            if m == 0:
                break
    
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
    while True:
        try:
            s.connect("\0comedisocket%d" % sockno)
            break
        except:
            pass

    try:
        blenderpath = (s.recv(1024)).decode('latin-1')
        s.send(b'ready')
    except:
        pass

    s.setblocking(0)

    return s, blenderpath

def disconnect(conn):
    sys.stdout.write('NICOMEDI: Received termination signal... ')
    sys.stdout.flush()
    while True:
        try:
            conn.sendall(b"quit")
            break
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

    databstr_full = b''
    t0 = time.time()
    while True:
        buffersize = c.comedi_get_buffer_contents(aichIC.dev, aichIC.subdev)
        if buffersize >= READBUFFER:
            try:
                databstr_full += os.read(aichIC.fd, aichIC.maxbuffer)
            except:
                sys.stdout.write("NICOMEDI: Reading from device failed\n")
                sys.stdout.flush()
    
        if buffersize < 0:
            sys.stdout.write("NICOMEDI: Warning: buffer error\n")
            comedi_errcheck()
            break
        elif buffersize > aichIC.maxbuffer/2:
            sys.stdout.write("NICOMEDI: Warning: buffer is more than half full\n")
        elif buffersize <= MINBUFFER:
            break    
    
#    t1 = time.time()   
#    sys.stdout.write("R {0:.02f}\n".format(t1-t0))
    if databstr_full == b'':
        # time.sleep(5e-4)
        return databstr_old

    databstr_full = databstr_old + databstr_full
    buffer12 = int(len(databstr_full)/12) * 12
    databstr = databstr_full[:buffer12]
    databstr_rem = databstr_full[buffer12:]
#    t2 = time.time()   
#    sys.stdout.write("C {0:.02f}\n".format(t2-t1))

    tmpIC, tmpEC, frames = databstr2np(databstr, [gainIC, gainEC], [aichIC, aichEC, aichFR])
#    t3 = time.time()   
#    sys.stdout.write("N {0:.02f}\n".format(t3-t2))
    ftmpIC.write(tmpIC.tostring()) 
    ftmpIC.flush()
    ftmpEC.write(tmpEC.tostring()) 
    ftmpEC.flush()
    ftmpFR.write(frames.tostring())
    ftmpFR.flush()
#    t4 = time.time()   
#    sys.stdout.write("F {0:.02f}\n".format(t4-t3))
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

def shutdown(aich):
    ret = c.comedi_close(aich.dev)
    if ret != 0:
        comedi_errcheck()

def set_trig(ch, state):
    ret = c.comedi_dio_write(ch.dev, ch.subdev, ch.no, state)
    if ret != 1:
        sys.stderr.write("NICOMEDI: Couldn't send trigger signal\n")
        comedi_errcheck()
