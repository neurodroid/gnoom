# C. Schmidt-Hieber, University College London
# 2011-03-21

import sys
import time

from nicomedilib import *

gAisubdev = 0
gAisubdevname = "/dev/comedi0_subd0"
gAichanIC = 0
gAichanEC = 7
gAichanFR = 15

gAosubdevname = "/dev/comedi0_subd1"
gAosubdev = 1
gAochanAO = 1

gDevrange = 0

gDt = 0.02 # ms
gPlot_sample = 4

gVc_gain = 10.0 # V/nA; gain=20
gCc_gain = 100.0e-3  # V/V; gain=100; convert to mV
gEC_gain = 1.0e3
gPulselength = 1.0e3 # ms
gConfigpath = "/home/cs/.comedi/ni_pcimio_pci-6281_comedi0"

gPulselengthN = int(gPulselength/gDt)
pulse_start = 0

if __name__=="__main__":

    if len(sys.argv) > 1:
        sockno = int(sys.argv[1])

    tbsw = np.ones((gPulselengthN), dtype=np.uint16) * 32768

    if has_comedi:
        c.comedi_loglevel(3)
        devaoch, fdaoch, nameaoch = open_dev(gAosubdevname)
    
        aochAO = nichannel(devaoch, gAochanAO, gAosubdev, fdaoch, gDevrange, calibrate=True,
                           configpath=gConfigpath)

        cmdao, chlistao = init_comedi_ao(aochAO, gDt, gPulselengthN)

        devaich, fdaich, nameaich = open_dev(gAisubdevname)
    
        aichIC = nichannel(devaich, gAichanIC, gAisubdev, fdaich, gDevrange, calibrate=True,
                           configpath=gConfigpath)
        aichEC = nichannel(devaich, gAichanEC, gAisubdev, fdaich, gDevrange, calibrate=True,
                           configpath=gConfigpath)
        aichFR = nichannel(devaich, gAichanFR, gAisubdev, fdaich, gDevrange, calibrate=True,
                           configpath=gConfigpath)
    
        cmdai = init_comedi_ai(aichFR, aichIC, aichEC, gDt)
    
    s, blenderpath = init_socket(sockno)
    connected = True

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
    timer = time0
    databstr_old = b''
    while True:
        time1 = time.time()
        if recording:
            if time.time()-timer > 0.01:
                databstr_old = \
                    read_buffer(aichIC, aichEC, aichFR, gCc_gain, gEC_gain, 
                                connic, connec, connfr, gPlot_sample, ftmpIC, ftmpEC, ftmpFR, databstr_old)
                # print(time.time()-timer)
                timer = time.time()    
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
 
        # Current pulses ============================================================
        if has_data and datadec.find('begintbs1') != -1:
            tbs_amp = int(datadec[
                datadec.find('tbs1')+4:datadec.find('tbs1')+10])
            for theta in range(0, int(gPulselength), 200):
                tbsw[int(float(theta)/gDt):int(float(theta+100)/gDt)] = 32768+tbs_amp

            sys.stdout.write("NICOMEDI: Pulse signal received\n")
            write_comedi_ao(aochAO, cmdao, tbsw)
            pulse_start = time.time()
        
        elif has_data and datadec.find('begintbst') != -1:
            tbs_amp = int(datadec[
                datadec.find('tbst')+4:datadec.find('tbst')+10])
            tbsw[int(float(0)/gDt):int(float(100)/gDt)] = 32768+tbs_amp

            sys.stdout.write("NICOMEDI: Pulse signal received\n")
            write_comedi_ao(aochAO, cmdao, tbsw)
            pulse_start = time.time()
        
        elif has_data and datadec.find('begintbs2') != -1:
            tbs_amp = int(datadec[
                datadec.find('tbs2')+4:datadec.find('tbs2')+10])
            
            for theta in range(0, int(gPulselength), 200):
                for many in range(0, 100, 10):
                    tbsw[int(float(theta+many)/gDt):int((theta+many+2.0)/gDt)] = 32768+tbs_amp #2ms pulse

            sys.stdout.write("NICOMEDI: Pulse signal received\n")
            write_comedi_ao(aochAO, cmdao, tbsw)
            pulse_start = time.time()
  
        elif has_data and datadec.find('begintbse') != -1:
            tbs_amp = int(datadec[
                datadec.find('tbse')+4:datadec.find('tbse')+10])
            for many in range(0, 100, 10):
                tbsw[int(float(many)/gDt):int((many+2.0)/gDt)] = 32768 + tbs_amp #2ms pulse

            sys.stdout.write("NICOMEDI: Pulse signal received\n")
            write_comedi_ao(aochAO, cmdao, tbsw)
            pulse_start = time.time()
        
        if time.time()-pulse_start > gPulselength*1e-3 and pulse_start > 0:
            print("NICOMEDI: stopping pulse")
            c.comedi_cancel(aochAO.dev, aochAO.subdev)
            cmdao = make_cmd_ao(aochAO.subdev, gDt, chlistao, 1, gPulselengthN)
            tbsw[:] = 32768
            pulse_start = 0
        # ============================================================================

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
        elif has_data and datadec.find('stop') != -1 and recording:
            stop(aichIC, aichEC, aichFR, gDt, "ms", "mV", "mV", gCc_gain, gEC_gain,
                 fn, ftmpIC, fntmpIC, ftmpEC, fntmpEC, ftmpFR, fntmpFR, entmp, s,
                 connic, connec, connfr, gPlot_sample, databstr_old)
            databstr_old = b''
            recording = False

        # Start the recording
        if has_data and datadec.find('h5') != -1 and \
                datadec.find('stop') == -1:
            if not recording:
                record(aichIC, cmdai, s)
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
