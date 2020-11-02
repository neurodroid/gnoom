# 2010-05-13, C. Schmidt-Hieber

import os
import sys
import time
import shutil
if 'numpy' not in sys.modules and hasattr(sys, '__numpy__'):
    # restore module cache with backup ref
    np = sys.modules['numpy'] = sys.__numpy__

else:
    import numpy as np
    # store a backup ref
    sys.__numpy__ = np
import bge.logic as GameLogic
import subprocess
import datetime
import settings
import nicomedilib as ncl
import bge
import copy

# $$$$$ CHANGED THIS BIT
try:
    import arduino_serial
    HAS_ARDUINO_SERIAL = True
except ImportError:
    HAS_ARDUINO_SERIAL = False

# $$$$$ CHANGED THIS
try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

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
if settings.replay_track is not None:
    sys.path.append(os.path.expanduser("~/../cs/py2p/tools"))
    import syncfiles

if sys.version_info >= (3,):
    import mathutils as mu
else:
    from Blender import Mathutils as mu


xmax = 10.0
ymax = 160.0


# converts seconds to a formatted string (hh:mm:ss)
def time2str(sec):
    nhs = int(sec/3600)
    nminutes = sec/60 - nhs*60
    nsecs = sec%60
    return ("%02d:%02d:%02d" % (nhs, nminutes, nsecs))

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
    if settings.reward_mode == "zone":
        reward_zone(pumppy, controller)
    elif not settings.cues:
        reward_linear(pumppy, controller)
    else:
        if GameLogic.Object["current_cues"] in settings.rewarded_cues:
            #print("ok")
            reward_linear(pumppy, controller)                

def reward_zone(pumppy, controller):
    if GameLogic.Object['RewardTicksCounter'] is not None:
        if GameLogic.Object['RewardTicksCounter'] == settings.reward_delay_ticks_pre and \
            not GameLogic.Object['RewardChange']:
            rand = np.random.uniform(0,1)
            if rand <= settings.reward_probability:
                if settings.gratings:
                    if GameLogic.Object["current_walls"] != settings.rewarded_env:
                        if settings.reward_zone2_start is not None and \
                            settings.reward_zone2_end is not None:
                            give_reward = True
                        else:
                            give_reward = False
                    else:
                        give_reward = True
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
                if GameLogic.Object["reward_zone_start"] is not None:
                    gio.write_reward(GameLogic.Object["reward_zone_start"], reward_success)
                else:
                    gio.write_reward(settings.reward_zone_start, reward_success)
            GameLogic.Object['RewardTicksCounter'] += 1

        elif GameLogic.Object['RewardTicksCounter'] == \
            settings.reward_delay_ticks_pre + settings.reward_delay_ticks_post:
            # Return animal with delay after reward
            GameLogic.Object['RewardChange'] = False
            GameLogic.Object['RewardTicksCounter'] += 1
            # we don't teleport the animal any longer - it has to get to the trigger point
            # zeroPos()

        elif GameLogic.Object['RewardTicksCounter'] >= \
            settings.reward_delay_ticks_pre + settings.reward_delay_ticks_post + 1:
            # Reward was just given, animal is back at beginning of track,
            # so it's now safe to return the pump
            GameLogic.Object['RewardChange'] = False
            # we don't teleport the animal any longer - it has to get to the trigger point
            # GameLogic.Object['RewardTicksCounter'] = None
            # zeroPos()
            # gc.zeroPump()
            # GameLogic.Object['WallTouchTicksCounter'] = None
        else:
            # Still touching pump but not long enough yet
            GameLogic.Object['RewardTicksCounter'] += 1
    else:
        # Entering reward zone
        sys.stdout.write("BLENDER: Entering reward zone\n")
        GameLogic.Object['RewardTicksCounter'] = 0
        # Could be used to buzz when entering the reward zone, currently disabled
        gc.runPump(pumppy, reward=False, buzz=False)

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
                    give_reward = True
                    if rand <= settings.reward_probability:
                        if settings.gratings:
                            give_reward = GameLogic.Object["current_walls"] == settings.rewarded_env
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
                        reward_delivered = reward_success and give_reward
                        gio.write_reward(newy, reward_delivered)
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

def zeroPos():
    tzeroPos = time.time()
    # controller = GameLogic.getCurrentController()
    # own = controller.owner
    scene = GameLogic.getCurrentScene()
    GameLogic.Object["lapCounter"] += 1
    print("Lap",  GameLogic.Object["lapCounter"])
    
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
        # set normal walls to invisible
        for i in scene.objects:
            if i.name[:8]=="LeftWall" or i.name[:9]=="RightWall": 
                i.visible=False
    if init and not settings.gratings :
        try:
            for objkey in ["LW1", "RW1", "CeilingGrating"]:
               scene.objects[objkey].visible=False
        except KeyError:
            sys.stderr.write("BLENDER: Warning: Grating walls are missing\n")
    if init and not settings.cues:
        try:
            for objkey in settings.objects_cues:
                try:
                    scene.objects[objkey].visible=False
                except KeyError:
                    sys.stderr.write(
                        "BLENDER: Warning: {0} is missing\n".format(objkey))
                    
        except AttributeError:
            sys.stderr.write("BLENDER: Warning: Cues are missing\n")
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
    if not settings.rotate_player:
        own.localOrientation = euler # [[0,0,0],[0,0,0],[0,0,0]]

    # Romain : randomly change wall gratings
    if settings.gratings:
        chooseWalls.randomWalls(settings.proba_env1)

    if not settings.looming:
        startOdorCounter()
        if settings.replay_track is None and not settings.rotate_player:
            own.localPosition = [0, settings.startPos, 1.5] # y was +80
        if init and settings.rotate_player:
            own.localPosition = [0, settings.startPos, 1.5]
  
        rew2 = scene.objects[rew2Name]
        rew3 = scene.objects[rew3Name]

        rew2.localPosition = [0, 1000, rew2.position[2]]
        rew3.localPosition = [0, 1000, rew3.position[2]]
        if settings.reward_mode == "zone":
            if GameLogic.Object["reward_zone_end"] is not None and \
                GameLogic.Object["reward_zone_start"] is not None:
                assert(GameLogic.Object["reward_zone_end"] > 
                    GameLogic.Object["reward_zone_start"])
            assert(settings.teleport_trigger_pos > settings.reward_zone_end)
            assert(settings.end_wall_pos > settings.teleport_trigger_pos)
            rew1 = scene.objects[rew1Name]
            rew1.localPosition = [0, 1000, rew1.position[2]]
            end_wall_pos_old = scene.objects['FrontWall.004'].localPosition
            scene.objects['FrontWall.004'].localPosition = [
                end_wall_pos_old[0], settings.end_wall_pos, end_wall_pos_old[2]]

    else:
        if settings.replay_track is None:
            own.localPosition = [0, 0, 0]

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

    
    if settings.cues or settings.gratings or settings.chunland:
        # gc.zeroPump()
        # GameLogic.Object['WallTouchTicksCounter']=None
        GameLogic.Object['RewardTicksCounter'] = None

    if settings.spatial_debug:
        try:
            if GameLogic.Object['light_off']:
                for object in scene.objects:
                    object.visible = False
        except:
            pass

    if time.time()-tzeroPos > 0.011:
        sys.stdout.write(
            'BLENDER: Warning: teleport took {0:.3f}ms\n'.format(
                (time.time()-tzeroPos)*1e3))

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

def light_flashes():
    ard = GameLogic.Object['arduino']
    if GameLogic.Object['file_open'] and not GameLogic.globalDict['light_switch']:
        GameLogic.Object['frameCounter'] += 1
        if GameLogic.Object['frameCounter'] < settings.flash_interval:
            pass
        elif GameLogic.Object['frameCounter'] == settings.flash_interval:
            gc.write_arduino_nonblocking(ard, b'1')
            #rd.write(('1').encode('latin-1'))
            gio.save_event('I0')
            print ("Flash on")
        elif GameLogic.Object['frameCounter'] > settings.flash_interval and GameLogic.Object['frameCounter'] < (settings.flash_interval + settings.flash_duration):
            pass
        elif GameLogic.Object['frameCounter'] == (settings.flash_interval + settings.flash_duration):
            GameLogic.Object['frameCounter'] = 0
            gc.write_arduino_nonblocking(ard, b'3')
            #ard.write(('3').encode('latin-1'))
            gio.save_event('I1')
            print ("Flash off")
    else:
        pass

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

    if side=='left':
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

    if settings.reward_mode == "zone":
        if GameLogic.Object["reward_zone_start"] is not None and \
            GameLogic.Object["reward_zone_end"] is not None:
            if ypos >= GameLogic.Object["reward_zone_start"] and ypos < GameLogic.Object["reward_zone_end"]:
                reward_central()
            # else:
            #     GameLogic.Object['RewardTicksCounter'] = None
        if ypos >= settings.teleport_trigger_pos and not settings.rotate_player:
            zeroPos()
        elif settings.rotate_player:
            if ypos >= settings.teleport_trigger_pos:
                # Make sure that we are on an outbound lap:
                if not GameLogic.Object['lapRotated'] and not GameLogic.Object['isRotating']:
                    GameLogic.Object['isRotating'] = True
                    GameLogic.Object['nframes_rotation'] = 0
            elif ypos < settings.startPos:
                # Make sure that we are on an inbound lap:
                if GameLogic.Object['lapRotated'] and not GameLogic.Object['isRotating']:
                    GameLogic.Object['isRotating'] = True
                    GameLogic.Object['nframes_rotation'] = 0

            if GameLogic.Object['isRotating']:
                if GameLogic.Object['nframes_rotation'] == 0:
                    tracked_speed = np.median(
                        np.abs(GameLogic.Object['speed_tracker'][-10:]))*1e2 * GameLogic.getLogicTicRate()
                    if tracked_speed != 0:
                        rotation_scale = settings.rotate_speed_scale / tracked_speed
                    else:
                        rotation_scale = settings.rotate_max_scale
                    if rotation_scale < settings.rotate_min_scale:
                        rotation_scale = settings.rotate_min_scale
                    if rotation_scale > settings.rotate_max_scale:
                        rotation_scale = settings.rotate_max_scale
                    GameLogic.Object['rotate_nframes_scaled'] = settings.rotate_nframes * rotation_scale
                # Freeze position while rotating:
                if GameLogic.Object['lapRotated']:
                    # Inbound lap (returning home), at start position
                    own.localPosition = (0, settings.startPos+2, 0)
                else:
                    # Outbound lap, at opposite end of corridor
                    own.localPosition = (0, settings.teleport_trigger_pos-2, 0) 
                if GameLogic.Object['nframes_rotation'] >= GameLogic.Object['rotate_nframes_scaled']:
                    # End of rotation
                    GameLogic.Object['isRotating'] = False
                    GameLogic.Object['lapRotated'] = not GameLogic.Object['lapRotated']
                    if GameLogic.Object['lapRotated']:
                        own.localOrientation = mu.Euler((0, 0, np.pi)).to_matrix()
                        gio.save_event('IN')
                    else:
                        own.localOrientation = mu.Euler((0, 0, 0)).to_matrix()
                        gio.save_event('OU')
                    zeroPos()
                    return
                else:
                    # Rotation
                    GameLogic.Object['nframes_rotation'] += 1
                    currentOrientation = own.localOrientation.to_euler()
                    own.localOrientation = mu.Euler((
                        currentOrientation[0],
                        currentOrientation[1],
                        (currentOrientation[2]+np.pi/GameLogic.Object['rotate_nframes_scaled']))).to_matrix()
                    return
    else:
        if np.fabs(xpos) > GameLogic.Object['boundx']:
            xpos = np.sign(xpos)*GameLogic.Object['boundx']
            own.localPosition = [xpos, ypos, zpos]

        if np.fabs(ypos) > GameLogic.Object['boundy']:
            own.localPosition = [xpos, np.sign(ypos)*GameLogic.Object['boundy'], zpos]

def move_player(move):
    if GameLogic.Object['isRotating']:
        return 0, 0, 0

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
        if GameLogic.Object['nreplay_rewards'] < len(GameLogic.Object['replay_rewards']) and \
            time.time()-GameLogic.Object['replay_time0'] >= \
            GameLogic.Object['replay_rewards'][GameLogic.Object['nreplay_rewards']]:
            print("BLENDER: Delivering replay reward no {0}".format(
                GameLogic.Object['nreplay_rewards']))
            GameLogic.Object['nreplay_rewards'] += 1
            gc.runPump(GameLogic.Object['pumppy'], reward=True, buzz=settings.reward_buzz)
            gio.write_reward(currentpos[1], True)

        newposx = GameLogic.Object['replay_pos'][0][GameLogic.Object['nreplay']]
        newposy = GameLogic.Object['replay_pos'][1][GameLogic.Object['nreplay']]
        newposz = GameLogic.Object['replay_pos'][2][GameLogic.Object['nreplay']]
        GameLogic.Object['nreplay'] += 1
        xtranslate = newposx-currentpos[0]
        ytranslate = newposy-currentpos[1]
        if settings.gratings:
            if ytranslate < syncfiles.TELEPORT_DETECT:
                chooseWalls.randomWalls(settings.proba_env1)
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

    if not settings.looming:
        controller.activate(act_ytranslate)
        
    return xtranslate, ytranslate, zrotate

def looming():

    playNextTrial=True
    
    if settings.singTrials:
        
        settings.loom_interval = [200]
    
        keyboard = GameLogic.keyboard
        JUST_ACTIVATED = GameLogic.KX_INPUT_JUST_ACTIVATED
    
        if keyboard.events[bge.events.LEFTALTKEY] == bge.logic.KX_INPUT_ACTIVE:
            
            #Set code
            if settings.objToLoom=="LoomSphere_Bright" and settings.outerSphereType=="OuterSphere_Blank_Bright":
                if ~settings.appearFlag:
                    str2='1'
                if settings.appearFlag:
                    str2='3'
            if settings.objToLoom=="LoomSphere_Bright" and settings.outerSphereType=="OuterSphere_Blank_Dark":
                if ~settings.appearFlag:
                    str2='2'
                if settings.appearFlag:
                    str2='4'
            if settings.objToLoom=="LoomSphere_Black" and settings.outerSphereType=="OuterSphere_Blank_Bright":
                if ~settings.appearFlag:
                    str2='5'
                if settings.appearFlag:
                    str2='7'
            if settings.objToLoom=="LoomSphere_Black" and settings.outerSphereType=="OuterSphere_Blank_Dark":
                if ~settings.appearFlag:
                    str2='6'
                if settings.appearFlag:
                    str2='8'
            
            # change looming position
            if keyboard.events[bge.events.FKEY] == JUST_ACTIVATED:
                 print("Loom type 0: Top!")
                 settings.loom_type= [0]
                 settings.playThisTrial=True
                 playNextTrial=False 
                 GameLogic.Object['loomcounter']=0
                 str1='U'
                 print(str1+str2)
                 #gio.save_event(str1+str2)
            if keyboard.events[bge.events.BKEY] == JUST_ACTIVATED:
                print("Loom type 1: Right!")
                settings.loom_type= [1]
                settings.playThisTrial=True
                playNextTrial=False 
                GameLogic.Object['loomcounter']=0
                str1='R'
                print(str1+str2)
                #gio.save_event(str1+str2)
            if keyboard.events[bge.events.CKEY] == JUST_ACTIVATED:
                 print("Loom type 2: Left!")
                 settings.loom_type= [2]
                 settings.playThisTrial=True
                 playNextTrial=False 
                 GameLogic.Object['loomcounter']=0
                 str1='L'
                 print(str1+str2)
                 #gio.save_event(str1+str2)
            if keyboard.events[bge.events.VKEY] == JUST_ACTIVATED:
                print("Loom type 3!")
                settings.loom_type= [3]
                settings.playThisTrial=True
                playNextTrial=False 
                GameLogic.Object['loomcounter']=0
                str1='M'
                print(str1+str2)
                #gio.save_event(str1+str2)
                
            # Change looming objects
            if keyboard.events[bge.events.LKEY] == JUST_ACTIVATED:
                if settings.loomNum < len(settings.allLoomObj)-1:
                    settings.loomNum+=1
                else:
                    settings.loomNum=0
                settings.objToLoom=settings.allLoomObj[settings.loomNum]
                print(settings.objToLoom)
                
            # Change background type
            if keyboard.events[bge.events.WKEY] == JUST_ACTIVATED:
                if settings.outerNum < len(settings.allOuterTypes)-1:
                    settings.outerNum+=1
                else:
                    settings.outerNum=0
                settings.outerSphereType=settings.allOuterTypes[settings.outerNum]
                print(settings.outerSphereType)
                
            # Change looming type: loom or appear
            if keyboard.events[bge.events.AKEY] == JUST_ACTIVATED:
                if settings.appearFlag:
                    settings.appearFlag=False
                else:
                    settings.appearFlag=True
                print('Stimuli Appear:',settings.appearFlag)
                
        
    scene = GameLogic.getCurrentScene()    
    
    # Make some objects disappear
    # All objects: 
    objectsToRemove=["LoomSphere_Lines","LoomSphere_Chequer",
                     "LoomSphere_Dots","LoomSphere_Lines_Concentric",
                     "LoomSphere_Black","LoomSphere_Bright",
                     "OuterSphere_Blank_Dark","OuterSphere_Blank_Bright","OuterSphere_Blank_Black",
                     "OuterSphere_Lines", "OuterSphere_Chequer"] #"OuterSphere_Blank",] # put the object name into quotes exple : ["name1","name2"]
    for obj in objectsToRemove:
        scene.objects[obj].visible=False

    circle = scene.objects[settings.objToLoom]
    circle.visible=True  
    outerSphere = scene.objects[settings.outerSphereType]
    outerSphere.visible=True
    outerSphere.worldPosition = (0,0,0)
    # -----------------------------------------------------------
    outerSphere.localScale=(1000,1000,1000)
    # -----------------------------------------------------------
    
    
 #   init_scale_up = [1.5, 1, 0]
 #   init_scale_down = [2, 1, 0]
    # ----------------------------------
    init_scale_up = [8, 8, 8]
    init_scale_down = [8, 8, 8]
    # ----------------------------------
    fin_scale = [0, 0, 0]
    speedscale = 2.0
    # SCALE WITH Z
    upDownRat=1.7
    xuprescale = ((0)*speedscale)/upDownRat 
    yuprescale = ((0)*speedscale)/upDownRat
    zuprescale = ((0)*speedscale)/upDownRat
    xdownrescale = (0)*speedscale 
    ydownrescale = (0)*speedscale 
    zdownrescale = (0)*speedscale
    # ORIGINAL POSITIONS ----------------------------
    #positions = np.array([(0, 50, 90), (0, 50, -15)])
    # NEW POSITIONS
    # ----------------------------------------------------------------
    currCamera=scene.objects["MainCamera.002"]
    startDist=300+currCamera.worldPosition[1]
    startHeight=200+currCamera.worldPosition[2]
    ## Above, In front, Right, Left
    #positions = np.array([(currCamera.worldPosition[0]+0,
    #                       currCamera.worldPosition[1] + np.sqrt(startDist*startDist - startHeight*startHeight) ,
    #                       currCamera.worldPosition[2] + startHeight),
    #                       (currCamera.worldPosition[0] + 0,
    #                       currCamera.worldPosition[1] + startDist ,
    #                       currCamera.worldPosition[2] + 0) , 
    #                       (currCamera.worldPosition[0] + startDist,
    #                       currCamera.worldPosition[1] + np.sqrt(startDist*startDist - startHeight*startHeight) ,
    #                       currCamera.worldPosition[2] + 0) , 
    #                       (currCamera.worldPosition[0] - startDist,
    #                       currCamera.worldPosition[1] + np.sqrt(startDist*startDist - startHeight*startHeight) ,
    #                       currCamera.worldPosition[2] + 0) ])
    

    #3 on the left. $ This can obviously be improved to take any length of startAngs$
    # NEXT fix up 2D version using camera worldpositions
    # And put 3D version onto remote computer
    startAngs=np.array([30, 70 , 70, 0])
    positions = np.array([(currCamera.worldPosition[0] + 0 ,
                           currCamera.worldPosition[1] + np.cos(np.deg2rad(startAngs[0]))*startDist,
                           currCamera.worldPosition[2] + np.sin(np.deg2rad(startAngs[0]))*startDist) ,
                           
                           (currCamera.worldPosition[0] + np.sin(np.deg2rad(startAngs[1]))*startDist,
                           currCamera.worldPosition[1] + np.cos(np.deg2rad(startAngs[1]))*startDist,
                           currCamera.worldPosition[2] + 0) ,
                           
                           (currCamera.worldPosition[0] - np.sin(np.deg2rad(startAngs[2]))*startDist,
                           currCamera.worldPosition[1] + np.cos(np.deg2rad(startAngs[2]))*startDist,
                           currCamera.worldPosition[2] + 0) ,
                           
                           (currCamera.worldPosition[0] + np.sin(np.deg2rad(startAngs[3]))*startDist,
                           currCamera.worldPosition[1] + np.cos(np.deg2rad(startAngs[3]))*startDist,
                           currCamera.worldPosition[2] + 0) ])
    # ----------------------------------------------------------------
    
    
    
    if type(settings.loom_interval)==list:
        # Make sure it starts on the 1st element of the list and not the 2nd
        if GameLogic.Object['totalLooms'] == 0:
            stop = settings.loom_interval[0]-(settings.loom_grow_dur+settings.loom_maintain_dur)# 30000-(grow_dur+maintain_dur)
        else:
            currLoomCond=(GameLogic.Object['totalLooms'] % len(settings.loom_interval))-1
            stop = settings.loom_interval[currLoomCond]-(settings.loom_grow_dur+settings.loom_maintain_dur)# 30000-(grow_dur+maintain_dur)
        print(GameLogic.Object['loomcounter']) ######
    else:
        stop = settings.loom_interval-(settings.loom_grow_dur+settings.loom_maintain_dur)# 30000-(grow_dur+maintain_dur)
    
    if (
        GameLogic.Object['train_open'] or GameLogic.Object['file_open']) and (
        GameLogic.Object['loom_first_trial'] < settings.loom_first_trial_delay):
        GameLogic.Object['loom_first_trial'] += 1
    elif ( ### HERE I THINK
        (GameLogic.Object['train_open'] or GameLogic.Object['file_open']) and settings.playThisTrial):
        #print("Start looming stimulus presentation")
        #print(GameLogic.Object['loomcounter'])

        if GameLogic.Object['loomcounter'] == 0:
            tracked_speed = np.median(np.abs(GameLogic.Object['speed_tracker']))*1e2 * GameLogic.getLogicTicRate()
            if tracked_speed > settings.loom_speed_threshold:
        # Start trial
                # Count the total number of trials that have occurred
                GameLogic.Object['totalLooms'] += 1
                
                GameLogic.Object['puffthistrial'] = random.randint(0,1)
                if settings.isloom_random:
                    GameLogic.Object['isloom'] = random.randint(0,1)
                else:
                    GameLogic.Object['isloom'] = 1
                print("BLENDER: Looming stimulus trial starting - running detected.Puff: "+str(GameLogic.Object['puffthistrial']))
                if settings.loom_random:
                    rand_pos_idx = random.randint(0, positions.shape[0]-1) ######## HERE HERE CHANGE TO ORDER
                    #rand_pos_idx = 3
                else:
                    if type(settings.loom_type)==list:
                        currLoomType=(GameLogic.Object['totalLooms'] % len(settings.loom_type))-1
                        rand_pos_idx=settings.loom_type[currLoomType]
                        print(rand_pos_idx)
                    else:
                        rand_pos_idx = settings.loom_type
                GameLogic.Object['rand_pos_idx'] = rand_pos_idx
                circle.worldPosition = positions[rand_pos_idx]
                
                if rand_pos_idx == 0:
                    if GameLogic.Object['isloom']: 
                         circle.localScale = init_scale_up
                    else:
                         circle.localScale = fin_scale
                # -----------------------------------------
                elif rand_pos_idx >= 1:
                # -----------------------------------------
                    if GameLogic.Object['isloom']: 
                         circle.localScale = init_scale_down
                    else:
                        circle.localScale = fin_scale
                GameLogic.Object['loomcounter'] += 1
                    
        elif GameLogic.Object['loomcounter'] < settings.loom_grow_dur + settings.loom_maintain_dur + stop:
            if GameLogic.Object['loomcounter'] < settings.loom_grow_dur:            
            # Change scale during trial
                minProximity= 10 #5 ###$$$
                if (GameLogic.Object['rand_pos_idx'] == 0 and GameLogic.Object['isloom']):
                    
                    # ------------------------------------------------------------
                    # This is my janky hack to convert positions to vectors
                    dummyPosLeg=scene.objects["RightLeg.002"]
                    dummyPosLeg.worldPosition=positions[GameLogic.Object['rand_pos_idx']]
                    
                    # $$ HERE calculate the trajectory of the object
                    directionVect=currCamera.worldPosition-dummyPosLeg.worldPosition
                    ## Make the trajectory a bit shorter so that the sphere doesn't intersect
                    trajectoryVect=np.multiply(directionVect,  np.divide(np.sqrt(sum(np.power(directionVect,2)))-minProximity,np.sqrt(sum(np.power(directionVect,2))))    )
                    stepPosChange=np.divide(trajectoryVect,settings.loom_grow_dur)

                    ## print(trajectoryVect)
                    circle.worldPosition = np.add(circle.worldPosition,stepPosChange)
                    # -----------------------------------------------------------------
                    
                    if settings.appearFlag:
                        circle.worldPosition = np.add(dummyPosLeg.worldPosition,trajectoryVect)
                    
                elif (GameLogic.Object['rand_pos_idx'] >= 1 and GameLogic.Object['isloom']):
                    
                    # ------------------------------------------------------------
                    # This is my janky hack to convert positions to vectors
                    dummyPosLeg=scene.objects["RightLeg.002"]
                    dummyPosLeg.worldPosition=positions[GameLogic.Object['rand_pos_idx']]
                    
                    # $$ HERE calculate the trajectory of the object
                    directionVect=currCamera.worldPosition-dummyPosLeg.worldPosition
                    ## Make the trajectory a bit shorter so that the sphere doesn't intersect
                    trajectoryVect=np.multiply(directionVect,  np.divide(np.sqrt(sum(np.power(directionVect,2)))-minProximity,np.sqrt(sum(np.power(directionVect,2))))    )
                    stepPosChange=np.divide(trajectoryVect,settings.loom_grow_dur)

                    ## print(trajectoryVect)
                    circle.worldPosition = np.add(circle.worldPosition,stepPosChange)
                    # -----------------------------------------------------------------
                    
                    if settings.appearFlag:
                        circle.worldPosition = np.add(dummyPosLeg.worldPosition,trajectoryVect)
                    
                    
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
        
    if ~playNextTrial and (GameLogic.Object['loomcounter'] > settings.loom_grow_dur + settings.loom_maintain_dur):
        settings.playThisTrial=False


def looming_2D():
    
    # Issue 1: screen is different: horizon too high
    # Issue 2" camera --> checking now
    
    scene = GameLogic.getCurrentScene()
    # Make some objects disappear
    # All objects: 
    objectsToRemove=["LoomSphere_Lines","LoomSphere_Chequer",
                     "LoomSphere_Dots","LoomSphere_Lines_Concentric",
                     "LoomSphere_Black","LoomSphere_Bright",
                     "OuterSphere_Blank_Dark","OuterSphere_Blank_Bright","OuterSphere_Blank_Black",
                     "OuterSphere_Lines", "OuterSphere_Chequer"] #"OuterSphere_Blank",] # put the object name into quotes exple : ["name1","name2"]
    for obj in objectsToRemove:
        scene.objects[obj].visible=False
    
    circle = scene.objects[settings.objToLoom]
    circle.visible=True  
    outerSphere = scene.objects[settings.outerSphereType]
    outerSphere.visible=True
    outerSphere.worldPosition = (0,0,0)
    outerSphere.localScale=(100,100,100)
                          

    baseSize=20.0
    init_scale_up = [baseSize, baseSize, baseSize]
    init_scale_down = [baseSize, baseSize, baseSize]
    fin_scale = [0, 0, 0]
    speedscale = 3.0
    # SCALE WITH Z
    upDownRat=1.2
    #xuprescale = ((0.5)*speedscale)/upDownRat #1
    #yuprescale = ((0.5)*speedscale)/upDownRat #1
    #zuprescale = ((0.3)*speedscale)/upDownRat #.3
    
    #xuprescale = ((0.5)*speedscale)/upDownRat #1
    #yuprescale = ((0.5)*speedscale)/upDownRat #1
    #zuprescale = ((0.3)*speedscale)/upDownRat #.3
    
    
    xdownrescale = (0.5)*speedscale #1
    ydownrescale = (0.5)*speedscale #1
    zdownrescale = (0.1)*speedscale #.45
    
    
    screenDist=120
    # ORIGINAL POSITIONS ----------------------------
    #positions = np.array([(0, 50, 90), (0, 50, -15)])
    # NEW POSITIONS
    startDist=100
    newDist=startDist
    startHeight=75
    startBack=20 
    appSpeed=3.5
    #appSpeed=3.9
    #positions = np.array([(0, np.sqrt(startDist*startDist - startHeight*startHeight) -20, startHeight),
    #                     (0, startDist-90.0, 0),
    #                     (-startDist, -startBack, 0),
    #                     (startDist, -startBack, 0)])
    
    #startHeight=100
    #positions = np.array([(0, np.sqrt(startDist*startDist - startHeight*startHeight) , startHeight)])
    
    upDownRat=1
    appSpeed=3.4
    xuprescale = xdownrescale
    yuprescale = xdownrescale
    zuprescale = xdownrescale
    
#    # Left vs right
#    positions = np.array([(-startDist, -startBack, 0),
#                         (startDist, -startBack, 0) ])
    
    # 3 on left - old method
    positions = np.array([(-startDist, -startBack, 0),
                         (-startDist/2, -startBack + startDist/2, 0) ,
                         (0, startDist-startBack, 0)])
    
#    # 3 on Left - new method
#    startDist=105
#    currCamera=scene.objects["MainCamera.002"]
#    startAngs=np.array([-60 , -30, 0])
#    positions = np.array([(currCamera.worldPosition[0] + np.sin(np.deg2rad(startAngs[0]))*startDist,
#                           currCamera.worldPosition[1] + np.cos(np.deg2rad(startAngs[0]))*startDist,
#                           currCamera.worldPosition[2] + 0) ,
#                           
#                           (currCamera.worldPosition[0] + np.sin(np.deg2rad(startAngs[1]))*startDist,
#                           currCamera.worldPosition[1] + np.cos(np.deg2rad(startAngs[1]))*startDist,
#                           currCamera.worldPosition[2] + 0) ,
#                           
#                           (currCamera.worldPosition[0] + np.sin(np.deg2rad(startAngs[2]))*startDist,
#                           currCamera.worldPosition[1] + np.cos(np.deg2rad(startAngs[2]))*startDist,
#                           currCamera.worldPosition[2] + 0) ])

    
                         
                         
    # $$ These should laer be changed to face the camera properly. but the fudge is good enough for now                     
    if settings.objToLoom =="LoomSphere_Lines_Concentric":
        allOrientations = np.array([(9.95, 0 , 0),
                                    (0, 0, 0),
                                    (0, 0, -1.95),
                                    (0, 0, 1.95)])
    else:
         allOrientations = np.array([(np.radians(90), 0 , 0),
                                    (np.radians(90), 0, 0),
                                    (np.radians(90), 0, 0),
                                    (np.radians(90), 0, 0)])
    # ------------------------------------------------
    if type(settings.loom_interval)==list:
        # Make sure it starts on the 1st element of the list and not the 2nd
        if GameLogic.Object['totalLooms'] == 0:
            stop = settings.loom_interval[0]-(settings.loom_grow_dur+settings.loom_maintain_dur)# 30000-(grow_dur+maintain_dur)
        else:
            currLoomCond=(GameLogic.Object['totalLooms'] % len(settings.loom_interval))-1
            stop = settings.loom_interval[currLoomCond]-(settings.loom_grow_dur+settings.loom_maintain_dur)# 30000-(grow_dur+maintain_dur)
    else:
        stop = settings.loom_interval-(settings.loom_grow_dur+settings.loom_maintain_dur)# 30000-(grow_dur+maintain_dur)

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
                # Count the total number of trials that have occurred
                GameLogic.Object['totalLooms'] += 1
                
                GameLogic.Object['puffthistrial'] = random.randint(0,1)
                if settings.isloom_random:
                    GameLogic.Object['isloom'] = random.randint(0,1)
                else:
                    GameLogic.Object['isloom'] = 1
                print("BLENDER: Looming stimulus trial starting - running detected.Puff: "+str(GameLogic.Object['puffthistrial']))
                if settings.loom_random:
                    rand_pos_idx = random.randint(0, positions.shape[0]-1) ######## HERE HERE CHANGE TO ORDER
                    #rand_pos_idx = 3
                else:
                    if type(settings.loom_type)==list:
                        currLoomType=(GameLogic.Object['totalLooms'] % len(settings.loom_type))-1
                        rand_pos_idx=settings.loom_type[currLoomType]
                        print(rand_pos_idx)
                    else:
                        rand_pos_idx = settings.loom_type
                GameLogic.Object['rand_pos_idx'] = rand_pos_idx
                circle.worldPosition = positions[rand_pos_idx]
                if settings.changeRotations:
                    circle.localOrientation = allOrientations[rand_pos_idx]
                if rand_pos_idx == 0:
                    if GameLogic.Object['isloom']: 
                         circle.localScale = [0,0,0]#init_scale_up
                    else:
                         circle.localScale = fin_scale
                elif rand_pos_idx >= 1:
                    if GameLogic.Object['isloom']: 
                         circle.localScale = [0,0,0]#init_scale_down
                    else:
                        circle.localScale = fin_scale
                GameLogic.Object['loomcounter'] += 1
                    
        elif GameLogic.Object['loomcounter'] < settings.loom_grow_dur + settings.loom_maintain_dur + stop:
            if GameLogic.Object['loomcounter'] < settings.loom_grow_dur:            
                # Change scale during trial
                
                if (GameLogic.Object['rand_pos_idx'] == 0 and GameLogic.Object['isloom']):
                    # newDist=newDist-10
                    #newDist+= startDist-appSpeed*float(GameLogic.Object['loomcounter'] )
                    #newScale=(baseSize/newDist)*screenDist
                    #circle.localScale.x =(xuprescale)*newScale
                    #circle.localScale.y =(yuprescale)*newScale
                    #circle.localScale.z =(zuprescale)*newScale
                    newDist+= startDist-appSpeed*float(GameLogic.Object['loomcounter'] )
                    newScale=(baseSize/newDist)*screenDist
                    circle.localScale.x =(xdownrescale)*newScale
                    circle.localScale.y =(ydownrescale)*newScale
                    circle.localScale.z =(zdownrescale)*newScale
                elif (GameLogic.Object['rand_pos_idx'] == 1 and GameLogic.Object['isloom']):
                    newDist+= startDist-appSpeed*float(GameLogic.Object['loomcounter'] )
                    newScale=(baseSize/newDist)*screenDist
                    circle.localScale.x =(xdownrescale)*newScale
                    circle.localScale.y =(ydownrescale)*newScale
                    circle.localScale.z =(zdownrescale)*newScale
                elif (GameLogic.Object['rand_pos_idx'] >= 2 and GameLogic.Object['isloom']):
                    # newDist=newDist-10
                    newDist+= startDist-appSpeed*float(GameLogic.Object['loomcounter'] )
                    newScale=(baseSize/newDist)*screenDist
                    circle.localScale.x =(xuprescale)*newScale
                    circle.localScale.y =(yuprescale)*newScale
                    circle.localScale.z =(zuprescale)*newScale
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

def looming_BASE():
 #   init_scale_up = [1.5, 1, 0]
 #   init_scale_down = [2, 1, 0]
    init_scale_up = [0, 0, 0]
    init_scale_down = [0, 0, 0]
    fin_scale = [0, 0, 0]
    speedscale = 2.0
    # ORIGINAL ---------------------------------
    #xuprescale = (2.34)*speedscale 
    #yuprescale = (1.56)*speedscale 
    #xdownrescale = (1.92)*speedscale 
    #ydownrescale = (0.96)*speedscale
    # NO CHANGE --------------------------------
    #xuprescale = (1)*speedscale 
    #yuprescale = (1)*speedscale 
    #xdownrescale = (1)*speedscale 
    #ydownrescale = (1)*speedscale
    # SCALE WITH Z
    upDownRat=1.7
    xuprescale = ((1)*speedscale)/upDownRat 
    yuprescale = ((1)*speedscale)/upDownRat
    zuprescale = ((.3)*speedscale)/upDownRat
    xdownrescale = (1)*speedscale 
    ydownrescale = (1)*speedscale 
    zdownrescale = (.45)*speedscale
    # ORIGINAL POSITIONS ----------------------------
    #positions = np.array([(0, 50, 90), (0, 50, -15)])
    # NEW POSITIONS
    startDist=100
    startHeight=75
    positions = np.array([(0, np.sqrt(startDist*startDist - startHeight*startHeight) , startHeight), (0, startDist, 0)])
    # ------------------------------------------------
    stop = settings.loom_interval-(settings.loom_grow_dur+settings.loom_maintain_dur)# 30000-(grow_dur+maintain_dur)

    circle = GameLogic.getCurrentScene().objects["LoomSphere"]
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
                    circle.localScale.z +=(zuprescale)
                elif (GameLogic.Object['rand_pos_idx'] == 1 and GameLogic.Object['isloom']):
                    circle.localScale.x +=(xdownrescale)
                    circle.localScale.y +=(ydownrescale)
                    circle.localScale.z +=(zdownrescale)
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
        
# -----------------------------------------------------------------------------------------------
# REMOVE IF DOESNT WORK -------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------       
def looming_3D():
 #   init_scale_up = [1.5, 1, 0]
 #   init_scale_down = [2, 1, 0]
    init_scale_up = [25, 25, 25]
    init_scale_down = [25, 25, 25]
    fin_scale = [0, 0, 0]
    speedscale = 2.0
    # ORIGINAL ---------------------------------
    #xuprescale = (2.34)*speedscale 
    #yuprescale = (1.56)*speedscale 
    #xdownrescale = (1.92)*speedscale 
    #ydownrescale = (0.96)*speedscale
    # NO CHANGE --------------------------------
    #xuprescale = (1)*speedscale 
    #yuprescale = (1)*speedscale 
    #xdownrescale = (1)*speedscale 
    #ydownrescale = (1)*speedscale
    # SCALE WITH Z
    upDownRat=1.7
    xuprescale = ((0)*speedscale)/upDownRat 
    yuprescale = ((0)*speedscale)/upDownRat
    zuprescale = ((0)*speedscale)/upDownRat
    xdownrescale = (0)*speedscale 
    ydownrescale = (0)*speedscale 
    zdownrescale = (0)*speedscale
    # ORIGINAL POSITIONS ----------------------------
    #positions = np.array([(0, 50, 90), (0, 50, -15)])
    # NEW POSITIONS
    startDist=100
    startHeight=75
    positions = np.array([(0, np.sqrt(startDist*startDist - startHeight*startHeight) , startHeight), (0, startDist, 0)])
    # ------------------------------------------------
    stop = settings.loom_interval-(settings.loom_grow_dur+settings.loom_maintain_dur)# 30000-(grow_dur+maintain_dur)

    circle = GameLogic.getCurrentScene().objects["LoomSphere"]
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
                    circle.localScale.z +=(zuprescale)
                    moveDir=-.5*(circle.worldPosition / np.sum(np.sqrt(circle.worldPosition)))
                    circle.worldPosition = [circle.worldPosition[0]+moveDir[0],
                                            circle.worldPosition[1]+moveDir[1],
                                            circle.worldPosition[2]+moveDir[2]]
                elif (GameLogic.Object['rand_pos_idx'] == 1 and GameLogic.Object['isloom']):
                    circle.localScale.x +=(xdownrescale)
                    circle.localScale.y +=(ydownrescale)
                    circle.localScale.z +=(zdownrescale)
                    moveDir=-1*(circle.worldPosition / np.sum(np.sqrt(circle.worldPosition)))
                    circle.worldPosition = [circle.worldPosition[0]+moveDir[0],
                                            circle.worldPosition[1]+moveDir[1],
                                            circle.worldPosition[2]+moveDir[2]]
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
# -----------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------

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
