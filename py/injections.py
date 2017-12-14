import bge.logic as GameLogic
import bge.events

import gnoomutils as gu
import gnoomio as gio
import gnoomcomm as gc

def inject():

    cont = GameLogic.getCurrentController()
    own = cont.owner
    keyboard = GameLogic.keyboard
    activated = GameLogic.KX_INPUT_JUST_ACTIVATED

    # Current pulses ============================================================
    # get position and set starting position and distance
    ypos = own.localPosition[1]
    linVelocity = own.getLinearVelocity(1)[1]
    linVel_thresh = 6.67 #MC2015 velocity hardcoded!!! based on 120 cm = 160 Blender units
    #if linVelocity > linVel_thresh:
    #    gu.save_event('VT')
    
    start_pulse_y_hysteresis = 10
    tbs2_factor = 5
    
    #add or subtract to total current injection applied
    if keyboard.events[bge.events.LEFTBRACKETKEY] == activated:
        GameLogic.Object['inj_amp'] = GameLogic.Object['inj_amp'] - 10
        print('current injection:', GameLogic.Object['inj_amp'])
    if keyboard.events[bge.events.RIGHTBRACKETKEY] == activated:
        GameLogic.Object['inj_amp'] = GameLogic.Object['inj_amp'] + 10
        print('current injection:', GameLogic.Object['inj_amp'])
        
    
    if GameLogic.Object['do_tbs1'] == False:
        if keyboard.events[bge.events.COMMAKEY] == activated:
            if GameLogic.Object['do_tbs2'] == False:
                GameLogic.Object['do_tbs2'] = True
                print('start tbs2')
                print(GameLogic.Object['start_pulse_y'])
            else:
                GameLogic.Object['do_tbs2'] = False
                print('stop tbs2')
            
    if GameLogic.Object['do_tbs2'] == False:
        if keyboard.events[bge.events.PERIODKEY] == activated:
            if GameLogic.Object['do_tbs1'] == False:
                GameLogic.Object['do_tbs1'] = True
                print('start tbs1')
                print(GameLogic.Object['start_pulse_y'])
            else:
                GameLogic.Object['do_tbs1'] = False
                print('stop tbs1')
    
    if keyboard.events[bge.events.EQUALKEY] == activated:
        tbst_amp = ncl.scale_ao_700b_cc(GameLogic.Object['inj_amp']) # pA
        gio.safe_send(conncomedi, "begintbst{0:+06d}send".format(tbst_amp),
                    "BLENDER: Couldn't send pulse\n")
        print('tbs1 test')
        gio.save_event('TT')
    if keyboard.events[bge.events.MINUSKEY] == activated:
        tbse_amp = ncl.scale_ao_700b_cc(GameLogic.Object['inj_amp']*tbs2_factor) # pA
        gio.safe_send(conncomedi, "begintbse{0:+06d}send".format(tbse_amp),
                    "BLENDER: Couldn't send pulse\n")
        print('tbs2 test')
        gio.save_event('TE')
        

    if ypos < GameLogic.Object['start_pulse_y']-start_pulse_y_hysteresis:
        if not GameLogic.Object['reset_pulse']:
            print("BLENDER: Reset pulse")
        GameLogic.Object['reset_pulse'] = True
       
    elif ypos >= GameLogic.Object['start_pulse_y'] and linVelocity > linVel_thresh and ypos < GameLogic.Object['start_pulse_y']+start_pulse_y_hysteresis: 
        if GameLogic.Object['reset_pulse']:
            if settings.has_comedi and ncl.has_comedi:
                if GameLogic.Object['do_tbs1']:
                    tbs1_amp = ncl.scale_ao_700b_cc(GameLogic.Object['inj_amp']) # pA
                    gc.safe_send(conncomedi, "begintbs1{0:+06d}send".format(tbs1_amp),
                                 "BLENDER: Couldn't send pulse\n")
                    gio.save_event('T1')
                    print('TBS1 current injected: ', GameLogic.Object['inj_amp'], 'pA \n', )
                elif GameLogic.Object['do_tbs2']:
                    tbs2_amp = ncl.scale_ao_700b_cc(GameLogic.Object['inj_amp']*tbs2_factor) # pA
                    gc.safe_send(conncomedi, "begintbs2{0:+06d}send".format(tbs2_amp),
                                 "BLENDER: Couldn't send pulse\n")
                    gio.save_event('T2')
                    print('TBS2 current injected: ', GameLogic.Object['inj_amp']*tbs2_factor, 'pA \n')
        GameLogic.Object['reset_pulse'] = False
    # ============================================================================