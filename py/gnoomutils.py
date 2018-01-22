# 2010-05-13, C. Schmidt-Hieber

import os
import sys
import time
import shutil
import numpy as np
import bge.logic as GameLogic
import subprocess
import datetime
import settings
import nicomedilib as ncl
import arduino_serial
import serial
import xinput
import random

import gnoomcomm as gc
import gnoomio as gio

if settings.gratings:
    import chooseWalls
    import cues
if settings.cues:
    import chooseCues
    import cues

if sys.version_info >= (3,):
    import mathutils as mu
else:
    from Blender import Mathutils as mu


xmax = 10.0
ymax = 160.0


# returns the area index corresponding to the coords:
def coordsToIndex(x,y):
    x += xmax
    y += ymax
    return int(int(x/xmax*2.0) + 4.0 * int(y/ymax*2.0))

# get boundaries for an area index:
def indexToBounds(index):
    x = np.remainder(index,4) * xmax/2.0
    y = int(index/4.0) * ymax/2.0

    return [x-xmax, x-xmax+xmax/2.0], [y-ymax, y-ymax+ymax/2.0]

# converts seconds to a formatted string (hh:mm:ss)
def time2str(sec):
    nhs = int(sec/3600)
    nminutes = sec/60 - nhs*60
    nsecs = sec%60
    return ("%02d:%02d:%02d" % (nhs, nminutes, nsecs))

# get new coordinates in a poorly visited area:
def newCoords():
    min = GameLogic.Object['visits'].min()
    minIndices = np.where(GameLogic.Object['visits']==min)[0]

    # pick out of least visited areas:
    minIndex = np.random.random_integers(0,len(minIndices)-1)
    minArea = minIndices[minIndex]

    # get boundaries for this index:
    xbound, ybound = indexToBounds(minArea)
    limitx = GameLogic.Object['boundx'] - (GameLogic.Object['hysteresis'])
    limity = GameLogic.Object['boundy'] - (GameLogic.Object['hysteresis'])

    if xbound[0] < -limitx:
        xbound[0] = -limitx
    if xbound[1] > limitx:
        xbound[1] = limitx
    if ybound[0] < -limity:
        ybound[0] = -limity
    if ybound[1] > limity:
        ybound[1] = limity
    newx = np.random.uniform(*xbound)
    newy = np.random.uniform(*ybound)
    # check
    actArea = coordsToIndex(newx,newy)

    return newx, newy



def gain_mode(gmode):
    GameLogic.Object["gain_mode"] = gmode
    save_event("G" + gmode[0].upper())

def reward_central():
    try:
        pumppy = GameLogic.Object['pumppy']
    except:
        pumppy = None
        
    # get controller
    controller = GameLogic.getCurrentController()
   
    if settings.linear:
        if not settings.cues:
            if settings.reward_double:
                reward_linear_double(pumppy, controller)
            elif settings.reward_cpp:
                reward_cpp(pumppy, controller)
            else:
                reward_linear(pumppy, controller)
        else:
            if GameLogic.Object["current_cues"] in settings.rewarded_cues:
                #print("ok")
                reward_linear(pumppy, controller)                
    else:
        reward_2d(pumppy, controller)


def reward_linear_double(pumppy, controller):

    scene = GameLogic.getCurrentScene()
    if scene.name == "Scene":
        teleportName = 'Cylinder.003'
    else:
        teleportName = 'Cylinder.000'

    if not 'SReward' in controller.sensors:
        return
    radar = controller.sensors['SReward']
    reward = radar.hitObject
    if reward is None:
        return
    if reward.name == teleportName:
        # This is not a reward in this case but a teleport detector
        if GameLogic.Object['RewardTicksCounter'] is not None:
            if GameLogic.Object['RewardTicksCounter'] == settings.reward_delay_ticks_pre + settings.reward_delay_ticks_post:
                zeroPos()
                GameLogic.Object['RewardTicksCounter'] += 1
            elif GameLogic.Object['RewardTicksCounter'] >= settings.reward_delay_ticks_pre + settings.reward_delay_ticks_post + 1:
                GameLogic.Object['RewardTicksCounter'] = None
                GameLogic.Object['WallTouchTicksCounter'] = None
            else:
                # Still touching pump but not long enough yet
                GameLogic.Object['RewardTicksCounter'] += 1
        else:
            # First reward touch, buzz and start counter
            GameLogic.Object['RewardTicksCounter'] = 0
            
        return
            
    # Move to fantasy land to avoid multiple rewards:
    oldy = reward.localPosition[1]
    reward.localPosition = [0,1000.0,reward.position[2]]
    if reward.name[-1] == GameLogic.Object['select_rew']:
        gc.runPump(pumppy, reward=True, buzz=settings.reward_buzz)
        GameLogic.Object['rewcount'] += 1
        reward_success = True
    else:    
        reward_success = False
        GameLogic.Object['rewfail'] += 1

    gio.write_reward(oldy, reward_success)

def reward_linear(pumppy, controller):
    
    if not 'SReward' in controller.sensors:
        return
    radar = controller.sensors['SReward']
    reward = radar.hitObject
    if GameLogic.Object['RewardTicksCounter'] is not None:
        if GameLogic.Object['RewardTicksCounter'] == settings.reward_delay_ticks_pre and not GameLogic.Object['RewardChange']:
            # Give reward
            if reward is not None:
                nrew = len(GameLogic.Object['rewpos'])
                newy = GameLogic.Object['rewpos'][np.mod(GameLogic.Object['rewcount'],nrew)] * settings.reward_pos_linear # newCoords()
                if GameLogic.Object['WallTouchTicksCounter'] is None:
                    rand = np.random.uniform(0,1)
                    if rand <= settings.reward_probability:
                        if settings.gratings:
                            give_reward = GameLogic.Object["current_walls"] == settings.rewarded_env
                        else:
                            give_reward = True
                        if settings.replay_track is None:
                            gc.runPump(pumppy, reward=give_reward, buzz=settings.reward_buzz)
                        GameLogic.Object['rewcount'] += 1
                        reward_success = True
                        #Matthias 2016/02/15
                        if settings.reward_delay_ticks_pre <= settings.reward_change_max:
                            settings.reward_delay_ticks_pre += settings.reward_change_step
                            print('\n{}'.format(settings.reward_delay_ticks_pre))
                            GameLogic.Object['RewardChange'] = True
                    else:
                        reward_success = False
                        GameLogic.Object['rewfail'] += 1

                    if settings.replay_track is None:
                        gio.write_reward(newy, reward_success)
                else:
                    sys.stdout.write('WallTouchTicksCounter is not None\n')
            GameLogic.Object['RewardTicksCounter'] += 1

        elif GameLogic.Object['RewardTicksCounter'] == settings.reward_delay_ticks_pre + settings.reward_delay_ticks_post:
            # Return animal with delay after reward
            if reward is not None:
                newx = 0
                # Move to fantasy land to avoid multiple rewards:
                reward.localPosition = [newx,1000.0,reward.position[2]]
            GameLogic.Object['RewardChange'] = False
            GameLogic.Object['RewardTicksCounter'] += 1
            zeroPos()

        elif GameLogic.Object['RewardTicksCounter'] >= settings.reward_delay_ticks_pre + settings.reward_delay_ticks_post + 1:
            # Reward was just given, animal is back at beginning of track,
            # so it's now safe to return the pump
            gc.zeroPump()
            GameLogic.Object['RewardChange'] = False
            GameLogic.Object['RewardTicksCounter'] = None
            GameLogic.Object['WallTouchTicksCounter'] = None
        else:
            # Still touching pump but not long enough yet
            GameLogic.Object['RewardTicksCounter'] += 1
    else:
        # First reward touch, buzz and start counter
        GameLogic.Object['RewardTicksCounter'] = 0
        # CSH 2013-11-19 Muted pump
        gc.runPump(pumppy, reward=False, buzz=False)

# added by Huayi 24/03/14 
def reward_cpp(pumppy, controller):
    
    scene = GameLogic.getCurrentScene()
    if scene.name == "Scene":
        teleportName = 'Cylinder.003'
    else:
        teleportName = 'Cylinder.000'
    
    if not 'SReward' in controller.sensors:
        return
    radar = controller.sensors['SReward']
    reward = radar.hitObject
    if reward is None:
        return
    if reward.name == teleportName:
        # This is not a reward in this case but a teleport detector
        if GameLogic.Object['RewardTicksCounter'] is not None:
            if GameLogic.Object['RewardTicksCounter'] == settings.reward_delay_ticks_pre + settings.reward_delay_ticks_post:
                zeroPos()
                GameLogic.Object['RewardTicksCounter'] += 1
            elif GameLogic.Object['RewardTicksCounter'] >= settings.reward_delay_ticks_pre + settings.reward_delay_ticks_post + 1:
                GameLogic.Object['RewardTicksCounter'] = None
                GameLogic.Object['WallTouchTicksCounter'] = None
            else:
                # Still touching pump but not long enough yet
                GameLogic.Object['RewardTicksCounter'] += 1
        else:
            # First reward touch, buzz and start counter
            GameLogic.Object['RewardTicksCounter'] = 0
            
        return
            
    # Move to fantasy land to avoid multiple rewards:
    oldy = reward.localPosition[1]
    reward.localPosition = [0,1000.0,reward.position[2]]
    gc.runPump(pumppy, reward=True, buzz=settings.reward_buzz)
    GameLogic.Object['rewcount'] += 1
    reward_success = True

    gio.write_reward(oldy, reward_success)
 
        
def reward_2d(pumppy, controller):
    if not 'SReward' in controller.sensors:
        return
    radar = controller.sensors['SReward']
    reward = radar.hitObject

    if reward is not None:
        gc.runPump(pumppy, buzz=settings.reward_buzz)
        nrew = len(GameLogic.Object['rewpos'])
        GameLogic.Object['rewcount'] += 1
        newx, newy = 0, GameLogic.Object['rewpos'][np.mod(GameLogic.Object['rewcount'],nrew)] * 145.0 # newCoords()
        reward.localPosition = [newx,newy,reward.position[2]]
							
        gio.write_reward(newy)

def zeroPos():
    # controller = GameLogic.getCurrentController()
    # own = controller.owner
    scene = GameLogic.getCurrentScene()

    
    # Romain
    # avoid multiple resettings
    # this is important here because the gratings are changed
    # when calling zeroPos and we don't want to have two events
    # associated with one resetting
    
    # finally I generalize it to all cases
    try : # if initialisation, "last_zero" still doesn't exist
        GameLogic.Object["last_zero"]
        init=0
    except:
        init=1
    if not init and (settings.gratings or settings.cues):
        if GameLogic.Object["last_zero"]<=3:
            pass # return
        
    if init and settings.gratings : 
        # Romain   
        # make some objects disappear
        objectsToRemove=[] # put the object name into quotes exple : ["name1","name2"]
        for i in objectsToRemove:
            scene.objects[i].visible=False
        # set normal walls to invisible
        for i in scene.objects:
            if i.name[:8]=="LeftWall" or i.name[:9]=="RightWall": 
                i.visible=False
    if init and not settings.gratings :
        try:
            for i in ["LW1", "RW1", "CeilingGrating"]:
                scene.objects[i].visible=False
        except KeyError:
            sys.stderr.write("BLENDER: Warning: Grating walls are missing")
    if init and not settings.cues:
        try:
            for i in settings.objects_cues:
                scene.objects[i].visible=False
        except AttributeError:
            sys.stderr.write("BLENDER: Warning: Cues are missing")
    GameLogic.Object["last_zero"]=0

    if scene.name == "Scene":
        playerName = 'MovingCube'
        rew1Name = 'Cylinder.001'
        rew2Name = 'Cylinder.002'
        rew3Name = 'Cylinder.003'
    elif scene.name == "Looming":
        playerName = 'MovingCube.002'
    else:
        playerName = 'MovingCube.001'
        rew1Name = 'Cone.001'
        rew2Name = 'Cone.002'
        rew3Name = 'Cylinder.000'
    own = scene.objects[playerName]
    if sys.version_info >= (3,):
        euler = mu.Euler((0,0,0))
        euler = euler.to_matrix()
    else:
        euler = mu.Euler(0, 0, 0)
    own.localOrientation = euler # [[0,0,0],[0,0,0],[0,0,0]]
    if settings.linear and not settings.looming:
        startOdorCounter()
        if settings.replay_track is None:
            own.localPosition = [0, settings.startPos, 1.5] # y was +80
        if settings.reward_double:
            
            # Randomly select one of the 2 rewards:
            GameLogic.Object['select_rew'] = "%s" % (np.random.randint(2)+1)
            
            # Distribute rewards with at least 20 units distance between the 2:
            rew1 = scene.objects[rew1Name]
            rew2 = scene.objects[rew2Name]
            new_rew_y = np.random.uniform(20.0, 120.0, 2)
            while np.diff(new_rew_y)[0] < 20.0:
                new_rew_y = np.random.uniform(20.0, 120.0, 2)
            rew1.localPosition = [0, new_rew_y[0], rew1.position[2]]
            rew2.localPosition = [0, new_rew_y[1], rew2.position[2]]
    
        elif settings.reward_cpp: 
            rew1 = scene.objects[rew1Name]
            rew2 = scene.objects[rew2Name]
            
            rew1.localPosition = [0, 60, rew1.position[2]]
            rew2.localPosition = [200, 0, rew2.position[2]]
        else:
            rew2 = scene.objects[rew2Name]
            rew3 = scene.objects[rew3Name]
            
            rew2.localPosition = [0, 1000, rew2.position[2]]
            rew3.localPosition = [0, 1000, rew3.position[2]]
            
    elif not settings.looming:
        if settings.replay_track is None:
            own.localPosition = [0, -150, 1.5]
    else:
        if settings.replay_track is None:
            own.localPosition = [0, 0, 0]

    # Romain : randomly change wall gratings
    if settings.gratings:
        chooseWalls.randomWalls(settings.proba_env1)
        
    # Romain : select the pair of cues either 'randomly without replacement' settings.groups_trials = True
    # or completely randomly if settings.groups_trials = False
    if settings.cues:
        if settings.groups_trials:
            if GameLogic.Object['run_number'] in [None,settings.n_runs-1]:
                if GameLogic.Object['run_number']==settings.n_runs-1:
                    GameLogic.Object["stopped_counter_sessions"]=0
                GameLogic.Object['run_number']=0
                GameLogic.Object['current_order']=chooseCues.generate_order(settings.content_trials)
                cues.write_new_session()
                print(GameLogic.Object['current_order'])
            else:
                GameLogic.Object['run_number']+=1
                GameLogic.Object["stopped_counter_trials"]=0
            chooseCues.chooseCues(GameLogic.Object['current_order'][GameLogic.Object['run_number']])
        else:
            chooseCues.randomCues(settings.proba_mismatch)

    if settings.cues or settings.gratings:
        # gc.zeroPump()
        # GameLogic.Object['WallTouchTicksCounter']=None
        # GameLogic.Object['RewardTicksCounter'] = None
        pass

def startOdorCounter():
    GameLogic.Object['OdorTicksCounter'] = 0
    scene = GameLogic.getCurrentScene()
    if scene.name == "Scene":
        gc.open_valve(3)
    else:
        gc.open_valve(2)
    
def incrementOdorCounter():
    if GameLogic.Object['OdorTicksCounter'] is not None:
        GameLogic.Object['OdorTicksCounter'] += 1
        if GameLogic.Object['OdorTicksCounter'] > settings.odor_ticks:
            GameLogic.Object['OdorTicksCounter'] = None
            # Close all scent valves, open unscented valve
            gc.open_valve(1)   


def airpuff_loom():
    ard = GameLogic.Object['arduino']
    if ard is not None:
        ard.write(('1').encode('latin-1'))
    gio.write_puff()


def airpuff_loom_stop():
    ard = GameLogic.Object['arduino']
    if ard is not None:
        ard.write(('3').encode('latin-1'))

    
def airpuff(side):
    if settings.cues:
        if GameLogic.Object["current_cues"] not in settings.rewarded_cues:
            zeroPos()
            return

    if side=='right':
        sensor = 'SRightTouch'
        broadcast = 'right_on'
        ard_code = 2
        ev_code = b'RC'
    elif side=='left':
        sensor = 'SLeftTouch'
        broadcast = 'left_on'
        ard_code = 1
        ev_code = b'LC'
    else:
        sys.stderr.write('GNOOMUTILS: Side %s does not exist in airpuff()\n' % side)

    ard = GameLogic.Object['arduino']

    # get controller
    controller = GameLogic.getCurrentController()
    touch = controller.sensors[sensor]
    state = touch.positive

    GameLogic.Object[broadcast] = state
    apply_puff =True
    if state:
        # Check that the animal didn't just get a reward:
        if GameLogic.Object['RewardTicksCounter'] is not None and \
                GameLogic.Object['RewardTicksCounter'] > settings.reward_delay_ticks_pre:
            apply_puff = False
    
    if apply_puff:
        if ard is not None:
            ard.write(('%d' % (np.fabs(state-1)*2 + ard_code)).encode('latin-1'))
        # if ncl.has_comedi:
        #     ncl.set_trig(outrightch, state)
    if GameLogic.Object['train_open'] and state and apply_puff:
        time1 = time.time()
        dt = time1 -  GameLogic.Object['train_tstart']
        # sys.stdout.write("%s %s collision %d\n" % (time2str(dt), side, state))
        GameLogic.Object['event_file'].write(np.array([dt,], dtype=np.float32).tostring())
        GameLogic.Object['event_file'].write(ev_code)
        GameLogic.Object['event_file'].flush()

    if settings.linear and side=='left':
        if GameLogic.Object['WallTouchTicksCounter'] is not None:
            if GameLogic.Object['WallTouchTicksCounter'] == settings.airpuff_delay_ticks:
                if apply_puff:
                    GameLogic.Object['puffcount'] += 1
                    gio.write_puff()
                GameLogic.Object['WallTouchTicksCounter'] += 1
                zeroPos()
            elif GameLogic.Object['WallTouchTicksCounter'] >= settings.airpuff_delay_ticks + 2:
                GameLogic.Object['RewardTicksCounter'] = None
                GameLogic.Object['WallTouchTicksCounter'] = None
            else:
                GameLogic.Object['WallTouchTicksCounter'] += 1
        else:
            GameLogic.Object['WallTouchTicksCounter'] = 0


    
def adjust_webcam():
    subprocess.Popen(['/usr/bin/uvcdynctrl', '--set', 'Exposure, Auto Priority', '0'])
    subprocess.Popen(['/usr/bin/uvcdynctrl', '--set', 'Exposure, Auto',          '1'])
    subprocess.Popen(['/usr/bin/uvcdynctrl', '--set', 'Exposure (Absolute)',   '300'])
    subprocess.Popen(['/usr/bin/uvcdynctrl', '--set', 'Focus',                 '100'])
    subprocess.Popen(['/usr/bin/uvcdynctrl', '--set', 'Gain',                  '200'])
    subprocess.Popen(['/usr/bin/uvcdynctrl', '--set', 'Contrast',               '64'])
    subprocess.Popen(['/usr/bin/uvcdynctrl', '--set', 'Brightness',            '162'])
    print("BLENDER: Adjusted webcam")


# correct position upon collision with boundary wall
def collision():
    if settings.replay_track is not None:
        return

    controller = GameLogic.getCurrentController()
    own = controller.owner

    pos = np.array(own.localPosition)
    xpos = pos[0]
    ypos = pos[1]
    zpos = pos[2]

    if np.fabs(xpos) > GameLogic.Object['boundx']:
        xpos = np.sign(xpos)*GameLogic.Object['boundx']
        own.localPosition = [xpos, ypos, zpos]

    if np.fabs(ypos) > GameLogic.Object['boundy']:
        own.localPosition = [xpos, np.sign(ypos)*GameLogic.Object['boundy'], zpos]

def move_player(move):

    controller = GameLogic.getCurrentController()
    own = controller.owner

    if settings.replay_track is not None:
        currentpos = own.localPosition
        if GameLogic.Object['nreplay'] >= len(GameLogic.Object['replay_pos'][0]):
            print("BLENDER: Reached end of replay track; starting over")
            GameLogic.Object['nreplay'] = 0
        if GameLogic.Object['nreplay'] == 0:
            GameLogic.Object['replay_time0'] = time.time()
            GameLogic.Object['nreplay_rewards'] = 0
        if time.time()-GameLogic.Object['replay_time0'] >= \
            GameLogic.Object['replay_rewards'][GameLogic.Object['nreplay_rewards']]:
            print("BLENDER: Delivering replay reward no {0}".format(
                GameLogic.Object['nreplay_rewards']))
            GameLogic.Object['nreplay_rewards'] += 1
            gc.runPump(GameLogic.Object['pumppy'], reward=True, buzz=settings.reward_buzz)
        newposx = GameLogic.Object['replay_pos'][0][GameLogic.Object['nreplay']]
        newposy = GameLogic.Object['replay_pos'][1][GameLogic.Object['nreplay']]
        newposz = GameLogic.Object['replay_pos'][2][GameLogic.Object['nreplay']]
        GameLogic.Object['nreplay'] += 1
        xtranslate = newposx-currentpos[0]
        ytranslate = newposy-currentpos[1]
        zrotate = 0
        own.localPosition = [newposx, newposy, newposz]
        # print(own.localPosition)
        return xtranslate, ytranslate, zrotate
        
    # Note that x is mirrored if the dome projection is used.
    xtranslate = 0 #
    ytranslate = 0
    zrotate = 0

    # Swap mice if we use only one mouse:
    ytranslate_move = move[3]
    if GameLogic.Object['m1conn'] is not None and GameLogic.Object['m2conn'] is None:
        ytranslate_move = move[1] * -1

    # y axis front mouse
    if len(ytranslate_move):
        # pass
        ytranslate = float(ytranslate_move.sum())/ settings.gain_trans2 * settings.gain_trans# 500.0   # 1.4e-5 m per reading
    # x axis front mouse / side mouse
    if len(move[0]) and len(move[2]):
        # pass
        zrotate = float((move[0].sum()+move[2].sum())/settings.gain_rot_ave_02)/ -settings.gain_rot2 * settings.gain_rot#-5000.0   

    # y axis side mouse
    if len(move[1]):
        # pass
        zrotate += float((move[1].sum())/settings.gain_rot_ave_1)/ settings.gain_rot2 * settings.gain_rot #-5000.0
        
    own = controller.owner
    # pos = np.array(own.position)

    # Get the actuators
    act_xtranslate = controller.actuators["xtranslate"]
    act_ytranslate = controller.actuators["ytranslate"]
    act_zrotate    = controller.actuators["zrotate"]

    GameLogic.Object['speed_tracker'][GameLogic.Object['nframes'] % len(GameLogic.Object['speed_tracker'])] = ytranslate_move.sum()*settings.calibration_x

    act_ytranslate.dLoc = [0.0, ytranslate, 0.0]
    act_ytranslate.useLocalDLoc = True
    # set the values
    if not settings.linear:
        act_xtranslate.dLoc = [xtranslate, 0.0, 0.0]
        act_xtranslate.useLocalDLoc = True
        act_zrotate.dRot = [0.0, 0.0, zrotate]
        act_zrotate.useLocalDRot = False

        # Use the actuators 
        controller.activate(act_xtranslate)
        controller.activate(act_zrotate)

    if not settings.looming:
        controller.activate(act_ytranslate)
        
    return xtranslate, ytranslate, zrotate


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
            GameLogic.Object['replay_pos'] = training.read_pos(fn_pos, 1e9, False)
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
    if settings.linear:
        GameLogic.Object['rewpos'] = [0.98] # 1.0 # np.zeros((16))
    else:
        GameLogic.Object['rewpos'] = [-0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25, 0.0, -0.25, -0.5, -0.75, -1.0] # 1.0 # np.zeros((16))
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

    if settings.has_webcam:
        sys.stdout.write("BLENDER: Starting webcam... ")
        sys.stdout.flush()
        if not settings.cpp:
            svid, connvid, addrvid, pvid = gc.spawn_process("\0vidsocket", ['python3 %s/py/webcam.py' % blenderpath,], shell=True)
        else:
            svid, connvid, addrvid, pvid = gc.spawn_process("\0vidsocket", ['%s/cpp/webcam/webcam' % blenderpath,], system=False)
        print ("done")
        connvid.send(GameLogic.Object['day_dir'].encode('latin-1'))
        gc.recv_ready(connvid)
        connvid.setblocking(0)
        GameLogic.Object['vidconn'] = connvid

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
    
    if settings.linear:
        rew_sensor.sensors['SReward'].usePosPulseMode = True
        touch_sensor.sensors['SLeftTouch'].usePosPulseMode = True
    else:
        rew_sensor.sensors['SReward'].usePosPulseMode = False
        touch_sensor.sensors['SLeftTouch'].usePosPulseMode = False
    GameLogic.Object['scene_changed'] = 0
    GameLogic.Object['scene_name'] = scene.name

    GameLogic.Object['reset_pulse'] = False
    
    #current injection variables
    #variables for current injection - MC2015
    GameLogic.Object['start_pulse_y'] = 50
    GameLogic.Object['inj_amp'] = 50
    GameLogic.Object['do_tbs1'] = False
    GameLogic.Object['do_tbs2'] = False
    
    zeroPos()
    gc.zeroPump()
    
def looming():
    init_scale_up = [1.5, 1, 0]
    init_scale_down = [2, 1, 0]
    fin_scale = [0, 0, 0]
    speedscale = 1.0
    xuprescale = (2.34)*speedscale 
    yuprescale = (1.56)*speedscale 
    xdownrescale = (1.92)*speedscale 
    ydownrescale = (0.96)*speedscale
    positions = np.array([(-10, 50, 90), (-10, 50, -15)])
    stop = settings.loom_interval-(settings.loom_grow_dur+settings.loom_maintain_dur)# 30000-(grow_dur+maintain_dur)

    circle = GameLogic.getCurrentScene().objects["Circle"]
    if (
        GameLogic.Object['train_open'] or GameLogic.Object['file_open']) and (
        GameLogic.Object['loom_first_trial'] < settings.loom_first_trial_delay):
        GameLogic.Object['loom_first_trial'] += 1
    elif (
        GameLogic.Object['train_open'] or GameLogic.Object['file_open']):
        #print("Start looming stimulus presentation")
        #print(GameLogic.Object['loomcounter'])

        if GameLogic.Object['loomcounter'] == 0:
            tracked_speed = np.median(np.abs(GameLogic.Object['speed_tracker']))*1e2 * GameLogic.getLogicTicRate()
            if tracked_speed > settings.loom_speed_threshold:
        # Start trial
                GameLogic.Object['puffthistrial'] = random.randint(0,1)
                if settings.isloom_random:
                    GameLogic.Object['isloom'] = random.randint(0,1)
                else:
                    GameLogic.Object['isloom'] = 1
                print("BLENDER: Looming stimulus trial starting - running detected.Puff: "+str(GameLogic.Object['puffthistrial']))
                if settings.loom_random:
                    rand_pos_idx = random.randint(0,len(positions)-1)
                else:
                    rand_pos_idx = 0
                GameLogic.Object['rand_pos_idx'] = rand_pos_idx
                circle.worldPosition = positions[rand_pos_idx]
                if rand_pos_idx == 0:
                    if GameLogic.Object['isloom']: 
                         circle.localScale = init_scale_up
                    else:
                         circle.localScale = fin_scale
                elif rand_pos_idx == 1:
                    if GameLogic.Object['isloom']: 
                         circle.localScale = init_scale_down
                    else:
                        circle.localScale = fin_scale
                GameLogic.Object['loomcounter'] += 1
                    
        elif GameLogic.Object['loomcounter'] < settings.loom_grow_dur + settings.loom_maintain_dur + stop:
            if GameLogic.Object['loomcounter'] < settings.loom_grow_dur:            
            # Change scale during trial
                if (GameLogic.Object['rand_pos_idx'] == 0 and GameLogic.Object['isloom']):
                    circle.localScale.x +=(xuprescale)
                    circle.localScale.y +=(yuprescale)
                elif (GameLogic.Object['rand_pos_idx'] == 1 and GameLogic.Object['isloom']):
                    circle.localScale.x +=(xdownrescale)
                    circle.localScale.y +=(ydownrescale)
            elif GameLogic.Object['loomcounter'] > settings.loom_grow_dur + settings.loom_maintain_dur:
            # Stop trial and wait
                circle.localScale= fin_scale
            if settings.loom_airpuff_delay is not None:
                 if (settings.puff_random and GameLogic.Object['puffthistrial']== 1) or not settings.puff_random:
                     if GameLogic.Object['loomcounter']%settings.puffint == settings.loom_airpuff_delay and \
                     GameLogic.Object['puffcount'] < settings.puffnb:
                          airpuff_loom()
                          GameLogic.Object['puffcount']+= 1
                     else:
                         airpuff_loom_stop()
                
            GameLogic.Object['loomcounter'] += 1
        else:
            # Restart
            GameLogic.Object['loomcounter'] = 0
            GameLogic.Object['puffcount'] = 0
    
    else:
        circle.localScale= fin_scale

    if GameLogic.Object['train_open'] or GameLogic.Object['file_open']:
        gio.write_looming(circle)

def detect_scene_change():
    # scene change requested; start counting
    # Opening and closing valve could depend on scene name and could use its own counter
    # Note that scene name changes between opening and closing the valve
    if GameLogic.Object['scene_changed']>0:
        sys.stdout.write("BLENDER: Scene change requested\n")
        GameLogic.Object['scene_changed'] += 1
        # open valve

    # reset the animal and the rewards 10 frames later
    # to make sure the scene has really changed
    # Better alternative: check that scene name has changed
    # over the previous state
    scene = GameLogic.getCurrentScene()
    if scene.name != GameLogic.Object['scene_name']:
        # scene has changed; do all the scene change stuff here
        sys.stdout.write("BLENDER: Took %d frames to actually change the scene\n" % GameLogic.Object['scene_changed'])
        zeroPos()
        gc.zeroPump()
        GameLogic.Object['scene_changed'] = 0
    
    GameLogic.Object['scene_name'] = scene.name

