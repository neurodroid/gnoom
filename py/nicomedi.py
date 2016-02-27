# C. Schmidt-Hieber, University College London
# 2011-03-21

import sys
import time

from nicomedilib import *

gAisubdev = 0
gAichanIC = 0
gAichanEC = 7
gAichanFR = 15

gDevrange = 0

gDt = 0.02 # ms
gPlot_sample = 4

gVc_gain = 10.0 # V/nA; gain=20
gCc_gain = 100.0e-3  # V/V; gain=100; convert to mV
gEC_gain = 1.0e3

gConfigpath = "/home/cs/.comedi/ni_pcimio_pci-6281_comedi0"

if __name__=="__main__":

    if len(sys.argv) > 1:
        sockno = int(sys.argv[1])

    if has_comedi:
        c.comedi_loglevel(3)
        devaich, fdaich, nameaich = open_dev("/dev/comedi0_subd0")
    
        aichIC = nichannel(devaich, gAichanIC, gAisubdev, fdaich, gDevrange, calibrate=True,
                           configpath=gConfigpath)
        aichEC = nichannel(devaich, gAichanEC, gAisubdev, fdaich, gDevrange, calibrate=True,
                           configpath=gConfigpath)
        aichFR = nichannel(devaich, gAichanFR, gAisubdev, fdaich, gDevrange, 
                               calibrate=True, configpath=gConfigpath)
    
        cmd = init_comedi_ai(aichFR, aichIC, aichEC, gDt)

    s, blenderpath, connected = init_socket(sockno)

    sic, connic, addric, pic, ntry = \
        spawn_process("\0icsocket", 
                      ['python2', '%s/py/wxplot.py' % blenderpath, '%d' % (gDt*gPlot_sample*1e3)])
    connic.send(blenderpath.encode('latin-1'))
    datadec = ""
    while datadec != 'ready':
       try:
          data = connic.recv(1024)
          datadec = data.decode('latin-1')
       except:
          pass
    connic.setblocking(0)

    sec, connec, addrec, pec, nec = spawn_process("\0ecsocket", start=False, ntry=ntry)
    connec.send(blenderpath.encode('latin-1'))
    datadec = ""
    while datadec != 'ready':
       try:
          data = connec.recv(1024)
          datadec = data.decode('latin-1')
       except:
          pass
    connec.setblocking(0)

    sfr, connfr, addrfr, pfr, nfr = spawn_process("\0frsocket", start=False, ntry=ntry)
    connfr.send(blenderpath.encode('latin-1'))
    datadec = ""
    while datadec != 'ready':
       try:
          data = connfr.recv(1024)
          datadec = data.decode('latin-1')
       except:
          pass
    connfr.setblocking(0)

    recording = False
    time0 = time.time()
    time1 = time0
    databstr_old = b''
    while True:
        time1 = time.time()
        if recording:
            databstr_old = \
                read_buffer(aichIC, aichEC, aichFR, gCc_gain, gEC_gain, 
                            connic, connec, connfr, gPlot_sample, ftmpIC, ftmpEC, ftmpFR, databstr_old)
        else:
            try:
                connic.sendall(b"alive")
            except:
                pass
        datadec = ""
        try:
            data = s.recv(1024)
            datadec = data.decode('latin-1')
            has_data = True
        except:
            has_data = False
        if not recording:
            time.sleep(1e-4)

        # No sensible update from blender in a long time, terminate process
        if (not has_data) or (has_data and datadec.find('1') == -1 and datadec.find('h5') == -1):
            if connected:
                t_disconnect = time.time()
            connected = False
            if time.time()-t_disconnect > 0.5:
                if recording:
                    stop(aichIC, aichEC, aichFR, gDt, "ms", "mV", "mV", gCc_gain, gEC_gain,
                         fn, ftmpIC, fntmpIC, ftmpEC, fntmpEC, ftmpFR, fntmpFR, entmp, s,
                         connic, connec, connfr, gPlot_sample, databstr_old)
                    databstr_old = b''
                disconnect(connic)
                break
        else:
            connected=True
            
        # Explicit quit signal
        if has_data and datadec.find('quit')!=-1:
            sys.stdout.write("NICOMEDI: Game over signal received\n")
            if recording:
                stop(aichIC, aichEC, aichFR, gDt, "ms", "mV", "mV", gCc_gain, gEC_gain,
                     fn, ftmpIC, fntmpIC, ftmpEC, fntmpEC, ftmpFR, fntmpFR, entmp, s,
                     connic, connec, connfr, gPlot_sample, databstr_old)
                databstr_old = b''
            disconnect(connic)
            s.send(b'close')
            break
            
        # Stop the recording
        if has_data and datadec.find('stop') != -1 and recording:
            stop(aichIC, aichEC, aichFR, gDt, "ms", "mV", "mV", gCc_gain, gEC_gain,
                 fn, ftmpIC, fntmpIC, ftmpEC, fntmpEC, ftmpFR, fntmpFR, entmp, s,
                 connic, connec, connfr, gPlot_sample, databstr_old)
            databstr_old = b''
            recording = False

        # Start the recording
        if has_data and datadec.find('h5') != -1 and \
                datadec.find('stop') == -1:
            if not recording:
                record(aichIC, cmd, s)
                sys.stdout.write("NICOMEDI: Starting acquisition\n")
                sent = False
                while not sent:
                    try:
                        s.send(b"primed")
                        sent = True
                    except:
                        pass
                sent = False
                # time stamp for first sample
                s.send(np.array([time.time(),], dtype=np.float64).tostring()) 
                if gPlot:
                    while not sent:
                        try:
                            connic.sendall(b"begin")
                            sent = True
                        except:
                            pass
                fn = datadec[datadec.find("begin")+5:datadec.find("end")]
                # send filename to plotting process:
                fntmpIC = fn[:-3] + "_IC.bin"
                fntmpEC = fn[:-3] + "_EC.bin"
                fntmpFR = fn[:-3] + "_FR.bin"
                entmp = fn[:-3] + "_edge.bin"
                sys.stdout.write("NICOMEDI: Writing to temporary files %s*\n" % fntmpIC)
                ftmpIC = open(fntmpIC, 'w+b')
                ftmpEC = open(fntmpEC, 'w+b')
                ftmpFR = open(fntmpFR, 'w+b')
                recording = True
            connected=True

    if has_comedi:
        shutdown(aichIC)
    s.close()
    sys.stdout.write("done\n")
    sys.stdout.flush()
    sys.exit(0)