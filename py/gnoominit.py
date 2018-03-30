import os
import sys
import time
import numpy as np
import bge.logic as GameLogic
import settings
import nicomedilib as ncl
import arduino_serial
import serial
import xinput
import random

import gnoomcomm as gc
import gnoomio as gio
import gnoomutils as gu

if settings.gratings:
    import chooseWalls
    import cues
if settings.cues:
    import chooseCues
    import cues


def init():
    if settings.looming:
        scene = GameLogic.getCurrentScene()
        scene.replace("Looming")
    
    GameLogic.Object = {}
    print("BLENDER: GameLogic object created")
    GameLogic.Object['closed'] = False
    GameLogic.setLogicTicRate(100)

    sys.stdout.write("BLENDER: Maximum number of logic frames per render frame: %d\n" % GameLogic.getMaxLogicFrame() )
    sys.stdout.write("BLENDER: Maximum number of physics frames per render frame: %d\n" % GameLogic.getMaxPhysicsFrame() )
    sys.stdout.write("BLENDER: Physics update frequency: %d Hz\n" % GameLogic.getPhysicsTicRate() )

    # open arduino and pump

    try:
        arduino = arduino_serial.SerialPort(settings.arduino_port, 19200)
        sys.stdout.write("BLENDER: Successfully opened arduino\n")
    except OSError:
        sys.stdout.write("BLENDER: Failed to open arduino\n")
        arduino = None
    GameLogic.Object['arduino'] = arduino
    if arduino is not None:
        arduino.write(b'd')
        # Set all valves to low
        arduino.write(b'6')
        arduino.write(b'8')
        arduino.write(b'0')
        arduino.write(b'f')

    try:
        pumppy = serial.Serial(settings.pump_port, 19200, timeout=1)
        sys.stdout.write("BLENDER: Successfully opened pump\n")
        gc.setPumpVolume(pumppy, settings.reward_volume)
    except:
        sys.stdout.write("BLENDER: Failed to open pump\n")
        pumppy = None

    if settings.replay_track is not None:
        fn_pos = settings.replay_track + '.position'
        if not os.path.exists(fn_pos):
            print("BLENDER: Could not find " + fn_pos)
            settings.replay_track = None
        else:
            sys.path.append(os.path.expanduser("~/../cs/py2p/tools"))
            import training
            print("BLENDER: Reading replay track from " + fn_pos)
            GameLogic.Object['replay_pos'] = training.read_pos(
                fn_pos, 1e9, False, meters=False)
            posy = GameLogic.Object['replay_pos'][1]
            evlist, timeev = training.read_events(
                settings.replay_track + ".events", teleport_times=None)
            GameLogic.Object['replay_rewards'] = np.array([
                ev.time for ev in evlist if ev.evcode == b'RE'])
            GameLogic.Object['replay_rewards'] = np.sort(GameLogic.Object['replay_rewards'])
            if settings.replay_rewards_shuffle:
                intervals = np.diff([0] + GameLogic.Object['replay_rewards'].tolist())
                intervals = np.random.permutation(intervals)
                print(intervals)
                GameLogic.Object['replay_rewards'] = np.cumsum(intervals)
            print("Replay reward times: ", GameLogic.Object['replay_rewards'])
            GameLogic.Object['nreplay'] = 0

    if settings.gratings:
        if not "grating1" in GameLogic.Object.keys():
            GameLogic.Object["grating1"] = chooseWalls.grating(
                ori=settings.verticalGratingAngle, sf=settings.verticalGratingScale)
            GameLogic.Object["grating2"] = chooseWalls.grating(
                ori=settings.obliqueGratingAngle, sf=settings.obliqueGratingScale)
#            for wallkey in ["LW1", "RW1"]:
#                chooseWalls.set_texture_buffer(
#                    GameLogic.Object["grating1"], wallkey)
#            for wallkey in ["LW2", "RW2"]:
#                chooseWalls.set_texture_buffer(
#                    GameLogic.Object["grating2"], wallkey)
#                

    if ncl.has_comedi:
        print("BLENDER: Found comedi library")
        gOuttrigsubdev = 2
        gOuttrigchan = 0
        gOutfrchan = 1
        gOutleftchan = 2
        gOutrightchan = 3
        gOutexpchan = 4
    
        gIntrigsubdev = 7
        gIntrigchan = 0
    
        gDevrange = 0
    
        # open ni trigger channels
        devintrigch, fdintrigch, nameintrigch = ncl.open_dev("/dev/comedi0_subd2")
        devouttrigch, fdouttrigch, nameouttrigch = ncl.open_dev("/dev/comedi0_subd11")
    
        intrigch = ncl.nichannel(devintrigch, gIntrigchan, gIntrigsubdev, fdintrigch, gDevrange) 
        outtrigch = ncl.nichannel(devouttrigch, gOuttrigchan, gOuttrigsubdev, fdouttrigch, gDevrange) 
        outfrch = ncl.nichannel(devouttrigch, gOutfrchan, gOuttrigsubdev, fdouttrigch, gDevrange) 
        outleftch = ncl.nichannel(devouttrigch, gOutleftchan, gOuttrigsubdev, fdouttrigch, gDevrange) 
        outrightch = ncl.nichannel(devouttrigch, gOutrightchan, gOuttrigsubdev, fdouttrigch, gDevrange) 
        outexpch = ncl.nichannel(devouttrigch, gOutexpchan, gOuttrigsubdev, fdouttrigch, gDevrange) #MC2015
    
        ncl.init_comedi_dig(intrigch, outtrigch, outfrch, outleftch, outrightch, 
            outexpch #MC2015
            )
    else:
        intrigch = None
        outtrigch = None
        outfrch = None
        outleftch = None
        outrightch = None
        outexpch = None #MC2015
    
    GameLogic.Object['intrigch'] = intrigch
    GameLogic.Object['outtrigch'] = outtrigch
    GameLogic.Object['outfrch'] = outfrch
    GameLogic.Object['outleftch'] = outleftch
    GameLogic.Object['outrightch'] = outrightch
    GameLogic.Object['outexpch'] = outexpch #MC2015

    GameLogic.Object['pumppy'] = pumppy
    GameLogic.Object['left_on'] = False
    GameLogic.Object['right_on'] = False

    GameLogic.Object['file_open'] = False
    GameLogic.Object['train_open'] = False
    GameLogic.Object['bcstatus'] = False

    gio.create_data_dir()
    GameLogic.Object['time0'] = time.time()
    GameLogic.Object['prevtime'] = time.time()
    GameLogic.Object['nframes'] = 0

    GameLogic.Object['rewcount'] = 0
    GameLogic.Object['rewfail'] = 0
    GameLogic.Object['puffcount'] = 0
    GameLogic.Object['puffthistrial'] = 0
    GameLogic.Object['isloom'] = 0
    GameLogic.Object['loomcounter']=0
    GameLogic.Object['loom_first_trial']=0
    GameLogic.Object['rewpos'] = [0.98] # 1.0 # np.zeros((16))
    GameLogic.Object['boundx'] =   8.0
    GameLogic.Object['boundy'] = 158.0
    GameLogic.Object['hysteresis'] = 0.5
    GameLogic.Object['speed_tracker'] = np.zeros((100))

    blenderpath = GameLogic.expandPath('//')
    
    if not settings.cpp:
        s1, conn1, addr1, p1 = gc.spawn_process("\0mouse0socket", ['python3', '%s/py/usbclient.py' % blenderpath, '0'])
        s2, conn2, addr2, p2 = gc.spawn_process("\0mouse1socket", ['python3', '%s/py/usbclient.py' % blenderpath, '1'])
    else:
        if settings.readlib=="xinput":
            mice = xinput.find_mice(model=settings.mouse)
            for mouse in mice:
                # xinput.set_owner(mouse) # Don't need this if using correct udev rule
                xinput.switch_mode(mouse)
            if settings.usezmq:
                procname = 'readout_zmq'
            else:
                procname = 'readout'
            if len(mice)>=1:
                s1, conn1, addr1, p1 = \
                    gc.spawn_process(
                        "\0mouse0socket", 
                        [('%s/cpp/generic-ev/' % blenderpath) + procname, '%d' % mice[0].evno, '0'],
                        usezmq=settings.usezmq)
            else:
                s1, conn1, addr1, p1 = None, None, None, None
            if len(mice)>=3:
                s2, conn2, addr2, p2 = \
                    gc.spawn_process(
                        "\0mouse1socket", 
                        [('%s/cpp/generic-ev/readout' % blenderpath) + procname, '%d' % mice[2].evno, '1'],
                        usezmq=settings.usezmq)
            else:
                s2, conn2, addr2, p2 = None, None, None, None
        elif settings.readlib=="libusb":
            s1, conn1, addr1, p1 = \
                gc.spawn_process("\0mouse1socket", 
                              ['%s/cpp/g500-usb/readout' % blenderpath, '1'])
            s2, conn2, addr2, p2 = \
                gc.spawn_process("\0mouse0socket", 
                              ['%s/cpp/g500-usb/readout' % blenderpath, '0'])
        else:    
            s1, conn1, addr1, p1, s2, conn2, add2, p2 = \
                None, None, None, None, None, None, None, None

    if settings.has_fw:
        if not settings.fw_local:
            GameLogic.Object['fwip'] = '' #"128.40.202.203"
            sfw, connfw, addrfw = gc.spawn_process_net(GameLogic.Object['fwip'])
            if connfw is None:
                settings.has_fw = False
        else:
            sys.stdout.write("BLENDER: Starting fw... ")
            sys.stdout.flush()
            sfw, connfw, addrfw, pfw = \
                gc.spawn_process("\0fwsocket", ['%s/cpp/dc1394/dc1394' % blenderpath,], #MC2015
                              system=False, addenv={"SDL_VIDEO_WINDOW_POS":"\"1280,480\""})
            print("done")

        connfw.send(GameLogic.Object['fw_trunk'].encode('latin-1'))
        gc.recv_ready(connfw)
        connfw.setblocking(0)
        GameLogic.Object['fwconn'] = connfw

    GameLogic.Object['has_fw'] = settings.has_fw

    if settings.has_usb3:
        sys.stdout.write("BLENDER: Starting usb3... ")
        sys.stdout.flush()
        susb3, connusb3, addrusb3, pusb3 = \
            gc.spawn_process("\0usb3socket", ['%s/cpp/usb3/arv-camera-test' % blenderpath,], #MC2015
                          system=False, addenv={"SDL_VIDEO_WINDOW_POS":"\"1280,480\""})
        print("done")

        connusb3.send(GameLogic.Object['fw_trunk'].encode('latin-1'))
        gc.recv_ready(connusb3)
        connusb3.setblocking(0)
        GameLogic.Object['usb3conn'] = connusb3

    GameLogic.Object['has_usb3'] = settings.has_usb3
    
    if settings.has_comedi and ncl.has_comedi:
        scomedi, conncomedi, addrcomedi, pcomedi = \
            gc.spawn_process("\0comedisocket", ['python3', '%s/py/nicomedi.py' % blenderpath,])

        conncomedi.send(blenderpath.encode('latin-1'))
        gc.recv_ready(conncomedi)
        conncomedi.setblocking(0)
        GameLogic.Object['comediconn'] = conncomedi

    if settings.has_licksensor:
        slick, connlick, addrlick, plick = \
            gc.spawn_process("\0licksocket", ['python3', '%s/py/licksensor.py' % blenderpath,])

        connlick.send(blenderpath.encode('latin-1'))
        gc.recv_ready(connlick)
        connlick.setblocking(0)
        GameLogic.Object['lickconn'] = connlick

    if settings.has_licksensor_piezo:
        slickpiezo, connlickpiezo, addrlickpiezo, plickpiezo = \
            gc.spawn_process("\0lickpiezosocket", ['python3', '%s/py/licksensorpiezo.py' % blenderpath,])

        connlickpiezo.send(blenderpath.encode('latin-1'))
        gc.recv_ready(connlickpiezo)
        connlickpiezo.setblocking(0)
        GameLogic.Object['lickpiezoconn'] = connlickpiezo

    if settings.cpp:
        for mconn in [conn1, conn2]:
            if mconn is not None:
                mconn.send(b'start')
                gc.recv_ready(mconn, usezmq=settings.usezmq)
                if not settings.usezmq:
                    mconn.setblocking(0)
 
    if len(mice):
        GameLogic.Object['m1conn'] = conn1
        GameLogic.Object['m2conn'] = conn2
    else:
        GameLogic.Object['m1conn'] = None
        GameLogic.Object['m2conn'] = None

    GameLogic.Object['tmprec'] = False
    GameLogic.Object['trainrec'] = False
    GameLogic.Object['RewardTicksCounter'] = None
    GameLogic.Object['RewardChange'] = False
    GameLogic.Object['WallTouchTicksCounter'] = None
    GameLogic.Object['OdorTicksCounter'] = None  
    
    GameLogic.Object['piezolicks'] = 0
    GameLogic.Object['piezoframes'] = 0
    GameLogic.Object['piezoframepause'] = 0
 
    
    scene = GameLogic.getCurrentScene()
    if scene.name == "Scene":
        playerName = 'MovingCube'
        legName = 'LeftLeg'
    elif scene.name == "Looming":
        playerName = 'MovingCube.002'
        legName = 'LeftLeg.002'
    else:
        playerName = 'MovingCube.001'
        legName = 'LeftLeg.001'
        
    rew_sensor = scene.objects[playerName]
    touch_sensor = scene.objects[legName]
    
    rew_sensor.sensors['SReward'].usePosPulseMode = True
    touch_sensor.sensors['SLeftTouch'].usePosPulseMode = True

    GameLogic.Object['scene_changed'] = 0
    GameLogic.Object['scene_name'] = scene.name

    GameLogic.Object['reset_pulse'] = False
    
    #current injection variables
    #variables for current injection - MC2015
    GameLogic.Object['start_pulse_y'] = 50
    GameLogic.Object['inj_amp'] = 50
    GameLogic.Object['do_tbs1'] = False
    GameLogic.Object['do_tbs2'] = False
    
    gu.zeroPos()
    gc.zeroPump()
