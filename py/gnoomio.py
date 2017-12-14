"""Write data to files"""
import bge.logic as GameLogic
import os
import datetime
import shutil

import settings
import gnoomutils as gu

gGid_vr_users=1001


def write_header(fnheader, fnmov, fnephys, ephysstart, ephysstop):
    hf = open(fnheader, 'w')
    hf.write("Movie file: %s\n" % fnmov)
    hf.write("Electrophysiology file: %s\n" % fnephys)
    hf.write("Electrophysiology start: %.15f\n" % ephysstart)
    hf.write("Electrophysiology stop: %.15f\n" % ephysstop)
    hf.close()

def write_settings(fngain):
    hf = open(fngain, 'w')
    hf.write("Animal: %.s\n" % settings.gAnimal)
    hf.write("gain_trans: %.8f\n" % settings.gain_trans)
    hf.write("gain_rot: %.8f\n" % settings.gain_rot)
    hf.write("gain_trans2: %.8f\n" % settings.gain_trans2)
    hf.write("gain_rot2: %.8f\n" % settings.gain_rot2)
    hf.write("gain_rot_ave_02: %.8f\n" % settings.gain_rot_ave_02)
    hf.write("gain_rot_ave_1: %.8f\n" % settings.gain_rot_ave_1)
    hf.close()
    
def create_data_dir():
    if os.uname()[0] == "Darwin":
        path = "/Users/%s/data/" % os.getlogin()
    else:
        # path = "/home/%s/data/" % os.getlogin()
        path = settings.gPath

    today = datetime.date.today()

    # check year
    year_dir = "%d/" % (today.year)
    if os.path.isdir("%s%s" % (path,year_dir)):
        print("BLENDER: Data directory for this year exists:", "%s%s" % (path,year_dir))
    else:
        os.umask(0)
        os.mkdir("%s%s" % (path,year_dir), 0o775)
        os.chown("%s%s" % (path,year_dir), -1, gGid_vr_users) # set grp to vr_users
        print("BLENDER: Data directory for this year was created:", "%s%s" % (path,year_dir))

    # check month
    month_dir = "%s%d-%02d/" % (year_dir,today.year,today.month)
    if os.path.isdir("%s%s" % (path,month_dir)):
        print("BLENDER: Data directory for this month exists:", "%s%s" % (path,month_dir))
    else:
        os.umask(0)
        os.mkdir("%s%s" % (path,month_dir), 0o775)
        os.chown("%s%s" % (path,month_dir), -1, gGid_vr_users) # set grp to vr-users
        print("BLENDER: Data directory for this month was created:", "%s%s" % (path,month_dir))

    # check day
    day_dir = "%s%d-%02d-%02d/" \
         % (month_dir, today.year, today.month, today.day)
    if os.path.isdir("%s%s" % (path,day_dir)):
        print("BLENDER: Data directory for today exists:", "%s%s" % (path,day_dir))
    else:
        os.umask(0)
        os.mkdir("%s%s" % (path,day_dir), 0o775)
        os.chown("%s%s" % (path,day_dir), -1, gGid_vr_users) # set grp to vr-users
        print("BLENDER: Data directory for today was created:", "%s%s" % (path,day_dir))

    # check day
    user_dir = "%s/%s/" \
         % (day_dir, settings.experimenter)
    if os.path.isdir("%s%s" % (path,user_dir)):
        print("BLENDER: Data directory for today exists:", "%s%s" % (path,user_dir))
    else:
        os.umask(0)
        os.mkdir("%s%s" % (path,user_dir), 0o775)
        os.chown("%s%s" % (path,user_dir), -1, gGid_vr_users) # set grp to vr-users
        print("BLENDER: Data directory for today was created:", "%s%s" % (path,user_dir))

    GameLogic.Object['day_dir'] = "%s%s" % (path, user_dir)
    GameLogic.Object['data_trunk'] = "%s%s%d%02d%02d" \
        % (path, user_dir, today.year, today.month, today.day)
    GameLogic.Object['fw_trunk'] = "%s%d%02d%02d" \
        % (user_dir, today.year, today.month, today.day)

def create_train_dir(animal):
    if os.uname()[0] == "Darwin":
        path = "/Users/%s/data/training" % os.getlogin()
    else:
        # path = "/home/%s/data/" % os.getlogin()
        path = "%s/training" % settings.gPath

    if os.path.isdir("%s/%s" % (path,animal)):
        print("BLENDER: Data directory for this animal exists:", "%s/%s" % (path,animal))
    else:
        os.umask(0)
        os.mkdir("%s/%s" % (path,animal), 0o775)
        os.chown("%s/%s" % (path,animal), -1, gGid_vr_users) # set grp to vr-users
        print("BLENDER: Data directory for this animal was created:", "%s/%s" % (path,animal))

    today = datetime.date.today()

    GameLogic.Object['train_dir'] = "%s/%s" % (path, animal)
    GameLogic.Object['train_trunk'] = "%s/%s/2p%d%02d%02d" \
        % (path, animal, today.year, today.month, today.day)

def get_next_filename(wildcard = "pck"):
    no = 0
    while True:
        next_file = "%s_%04d.%s" \
            % (GameLogic.Object['data_trunk'], no, wildcard)
        if not os.path.isfile(next_file):
            fw_file = "%s_%04d.%s" \
                % (GameLogic.Object['fw_trunk'], no, wildcard)
            return next_file, fw_file
        no += 1

def get_next_trainname(wildcard = "bin"):
    no = 0
    while True:
        next_file = "%s_%04d.%s" \
            % (GameLogic.Object['train_trunk'], no, wildcard)
        if not os.path.isfile(next_file):
            return next_file
        no += 1
        
def write_reward(newy, reward_success=True):
    if GameLogic.Object['train_open'] or GameLogic.Object['file_open']:
        time1 = time.time()
        if GameLogic.Object['train_open']:
            dt = time1 -  GameLogic.Object['train_tstart']
        else:
            dt = time1 -  GameLogic.Object['time0']
        try:
            GameLogic.Object['event_file'].write(np.array([dt,], dtype=np.float32).tostring())
        except ValueError:
            sys.stderr.write("BLENDER: Error - writing to closed reward file\n")
            return
        if reward_success:
            sys.stdout.write("%s Reward %d; position: %d\n" % (gu.time2str(dt), GameLogic.Object['rewcount'], newy))
            GameLogic.Object['event_file'].write(b'RE')
        else:
            sys.stdout.write("%s No reward %d; position: %d\n" % (gu.time2str(dt), GameLogic.Object['rewfail'], newy))
            GameLogic.Object['event_file'].write(b'RF')
        GameLogic.Object['event_file'].flush()

#        if GameLogic.Object['file_open']:
#            pickle.dump(("reward", newx, newy),
#                         GameLogic.Object['current_file'], 2)
#

def write_licks(licks):
    if GameLogic.Object['train_open'] or GameLogic.Object['file_open']:
        for nlick in range(licks.shape[0]):
            if licks[nlick, 1] > 0:
                time1 = licks[nlick, 0]
                if GameLogic.Object['train_open']:
                   dt = time1 -  GameLogic.Object['train_tstart']
                else:
                   dt = time1 -  GameLogic.Object['time0']
                
                for nl in range(int(np.round(licks[nlick, 1]))):
                    GameLogic.Object['event_file'].write(np.array([dt,], dtype=np.float32).tostring())
                    sys.stdout.write("%s lick\n" % (gu.time2str(dt)))
                    GameLogic.Object['event_file'].write(b'LI')
                    GameLogic.Object['event_file'].flush()
                    
def write_valve(cmd):
    if GameLogic.Object['train_open'] or GameLogic.Object['file_open']:
        time1 = time.time()
        if GameLogic.Object['train_open']:
           dt = time1 -  GameLogic.Object['train_tstart']
        else:
           dt = time1 -  GameLogic.Object['time0']

        GameLogic.Object['event_file'].write(np.array([dt,], dtype=np.float32).tostring())
        GameLogic.Object['event_file'].write(b'V' + cmd)
        GameLogic.Object['event_file'].flush()

def write_puff():
    if GameLogic.Object['train_open'] or GameLogic.Object['file_open']:
        time1 = time.time()
        if GameLogic.Object['train_open']:
           dt = time1 -  GameLogic.Object['train_tstart']
        else:
           dt = time1 -  GameLogic.Object['time0']

        GameLogic.Object['event_file'].write(np.array([dt,], dtype=np.float32).tostring())
        sys.stdout.write("%s Airpuff %d\n" % (gu.time2str(dt), GameLogic.Object['puffcount']))
        GameLogic.Object['event_file'].write(b'AP')
        GameLogic.Object['event_file'].flush()

def save_event(ev_code):
    if GameLogic.Object['train_open'] or GameLogic.Object['file_open']:
        time1 = time.time()
        if GameLogic.Object['train_open']:
           dt = time1 -  GameLogic.Object['train_tstart']
        else:
           dt = time1 -  GameLogic.Object['time0']

        GameLogic.Object['event_file'].write(np.array([dt,], dtype=np.float32).tostring())
        sys.stdout.write("%s Saved event %s\n" % (gu.time2str(dt),ev_code))
        GameLogic.Object['event_file'].write(ev_code.encode('utf_8'))
        GameLogic.Object['event_file'].flush()

def write_training_file(move):
    # get controller
    controller = GameLogic.getCurrentController()
    own = controller.owner
     
    has_fw =  GameLogic.Object['has_fw']
    if has_fw:
        connfw = GameLogic.Object['fwconn']
    else:
        connfw = None

    time1 = time.time()
    dt = time1 - GameLogic.Object['train_tstart']

    if has_fw:
        frametimefw = parse_frametimes(connfw)-GameLogic.Object['time0']
    else:
        frametimefw = np.array([0,])
    sys.stdout.write("%s\r" % (gu.time2str(dt)))

    GameLogic.Object['train_file'].write(np.array([dt,
        len(move[0]), len(move[2])], dtype=np.float32).tostring())
    # 0:x1, 1:y1, 2:x2, 3:y2, 4:t1, 5:t2, 6:dt1, 7:dt2
    GameLogic.Object['train_file'].flush()
    if len(move[0]):
        GameLogic.Object['train_file'].write(np.array([
            move[0].sum(), move[1].sum()], dtype=np.float32).tostring())
    if len(move[2]):
        GameLogic.Object['train_file'].write(np.array([
            move[2].sum(), move[3].sum()], dtype=np.float32).tostring())
    if len(move[0]) or len(move[2]):
        GameLogic.Object['train_file'].flush()
    GameLogic.Object['pos_file'].write(np.array([ 
                xtranslate, ytranslate, zrotate, 
                own.position[0], own.position[1], own.position[2],
                own.orientation[0][0], own.orientation[0][1], own.orientation[0][2], 
                own.orientation[1][0], own.orientation[1][1], own.orientation[1][2], 
                own.orientation[2][0], own.orientation[1][2], own.orientation[2][2],
                ], dtype=np.float64).tostring())
    GameLogic.Object['pos_file'].flush()
    
def close_training_file():
    GameLogic.Object['train_file'].close()
    GameLogic.Object['event_file'].close()
    GameLogic.Object['pos_file'].close()
    if settings.looming:
        GameLogic.Object['current_loomfile'].close()
        GameLogic.Object['loomcounter'] = 0
        GameLogic.Object['loom_first_trial'] = 0
    train_tend = time.time()-GameLogic.Object['train_tstart']
    sys.stdout.write("BLENDER: Closing file; recorded %s of training\n" % (gu.time2str(train_tend)))
    GameLogic.Object['train_open'] = False
    if GameLogic.Object['has_fw']:
        gc.safe_send(GameLogic.Object['fwconn'], 'stop', '')
        
def start_training_file():
    # Start recordings
    create_train_dir(settings.gAnimal)
    fn = get_next_trainname("move")
    fn_events = fn[:-4] + "events"
    fn_pos = fn[:-4] + "position"
    sys.stdout.write("BLENDER: Writing training to:\n") 
    sys.stdout.write("         %s\n" % fn)
    sys.stdout.write("         %s\n" % fn_events)
    GameLogic.Object['train_file'] = open(fn, 'wb')
    GameLogic.Object['event_file'] = open(fn_events, 'wb')
    GameLogic.Object['pos_file'] = open(fn_pos, 'wb')
    if settings.looming:
        GameLogic.Object['current_loomfile'] = open(
            fn[:-5] + "_loom", 'wb')
    GameLogic.Object['current_fwfile'] = fn[:-4] + "avi"
    if GameLogic.Object['has_fw']:
        gc.safe_send(GameLogic.Object['fwconn'], "begin%send" % GameLogic.Object['current_fwfile'],
                  "BLENDER: Couldn't start video; resource unavailable\n")

    GameLogic.Object['train_tstart'] = time.time()
    GameLogic.Object['train_open'] = True

    # Copy current settings:
    fn_settings_py = fn[:-4] + "_settings.py"
    blenderpath = GameLogic.expandPath('//')
    shutil.copyfile('%s/py/settings.py' % blenderpath, fn_settings_py)

    # line break for printing time:
    sys.stdout.write("\n")

def write_record_file(move):
    time1 = time.time()
    dt = time1 -  GameLogic.Object['time0']
    arduino = GameLogic.Object['arduino']
    controller = GameLogic.getCurrentController()
    own = controller.owner
    
    if GameLogic.Object['bcstatus']==False:
        if arduino is not None:
            write_arduino_nonblocking(arduino, b'u')
        if settings.has_comedi and ncl.has_comedi:
            ncl.set_trig(GameLogic.Object['outfrch'], 1)
        GameLogic.Object['bcstatus']=True
    else:
        if arduino is not None:
            write_arduino_nonblocking(arduino, b'd')
        if settings.has_comedi and ncl.has_comedi:
            ncl.set_trig(GameLogic.Object['outfrch'], 0)
        GameLogic.Object['bcstatus']=False
    # if settings.has_webcam:
    #     frametime = parse_frametimes(connvid)-GameLogic.Object['time0']
    # else:
    #     frametime = np.array([0,])
    if GameLogic.Object['has_fw']:
        frametimefw = parse_frametimes(GameLogic.Object['fwconn'])-GameLogic.Object['time0']
    else:
        frametimefw = np.array([0,])
    GameLogic.Object['current_file'].write(np.array([dt, 
        xtranslate, ytranslate, zrotate, 
        own.position[0], own.position[1], own.position[2],
        time1,
        own.orientation[0][0], own.orientation[0][1], own.orientation[0][2], 
        own.orientation[1][0], own.orientation[1][1], own.orientation[1][2], 
        own.orientation[2][0], own.orientation[1][2], own.orientation[2][2],
        len(move[0]), len(move[2]), len(frametimefw)], dtype=np.float64).tostring())
    # 0:x1, 1:y1, 2:x2, 3:y2, 4:t1, 5:t2, 6:dt1, 7:dt2
    GameLogic.Object['current_file'].flush()
    for nm in range(len(move[0])):
        GameLogic.Object['current_file'].write(np.array([
            move[0][nm], move[1][nm], move[4][nm], move[6][nm]], dtype=np.float64).tostring())
    for nm in range(len(move[2])):
        GameLogic.Object['current_file'].write(np.array([
            move[2][nm], move[3][nm], move[5][nm], move[7][nm]], dtype=np.float64).tostring())
    if (len(move[0]) or len(move[2])):
        GameLogic.Object['current_file'].flush()
    if len(frametimefw) > 0:
        GameLogic.Object['current_file'].write(frametimefw.tostring())
        GameLogic.Object['current_file'].flush()
        
def stop_record_file():
    arduino = GameLogic.Object['arduino']

    # Close video and ephys acquisition
    if settings.has_webcam:
        gc.safe_send(GameLogic.Object['vidconn'], 'stop', '')
    if GameLogic.Object['has_fw']:
        gc.safe_send(GameLogic.Object['fwconn'], 'stop', '')
    GameLogic.Object['bcstatus']=False
    if settings.has_comedi and ncl.has_comedi:
        gc.safe_send(GameLogic.Object['comediconn'], 'stop', '')
        ncl.set_trig(GameLogic.Object['outtrigch'], 0)
        ncl.set_trig(GameLogic.Object['outfrch'], 0)
    
        # get ephys end time:
        ephysstop = (parse_ephystimes(GameLogic.Object['comediconn'])-GameLogic.Object['time0'])[0]
    else:
        # TODO: get correct intan ephys end time
        ephysstop = time.time()-GameLogic.Object['time0']
    if arduino is not None:
        write_arduino_nonblocking(arduino, b'd')

    GameLogic.Object['event_file'].close()
    GameLogic.Object['current_file'].close()
    if settings.looming:
        GameLogic.Object['current_loomfile'].close()
        GameLogic.Object['loomcounter'] = 0
        GameLogic.Object['loom_first_trial'] = 0
    print("BLENDER: Closing file")
    GameLogic.Object['file_open'] = False

    write_header(GameLogic.Object['current_movfile'][:-4]+"_header.txt", 
                    GameLogic.Object['current_movfile'], 
                    GameLogic.Object['current_ephysfile'],
                    GameLogic.Object['ephysstart'], ephysstop)
                    
def start_record_file():
    # Start recordings
    fn, fnfw = get_next_filename("bin")
    sys.stdout.write("BLENDER: Writing to:\n") 
    sys.stdout.write("         %s\n" % fn)
    GameLogic.Object['file_open'] = True
    GameLogic.Object['current_file'] = open(fn, 'wb')
    GameLogic.Object['current_movfile'] = fn[:-3] + "avi"
    if settings.looming:
        GameLogic.Object['current_loomfile'] = open(
            fn[:-4] + "_loom", 'wb')
    GameLogic.Object['current_fwfile'] = fnfw[:-3] + "avi"
    GameLogic.Object['current_ephysfile'] = fn[:-3] + "h5"
    GameLogic.Object['current_settingsfile'] = fn[:-4] + "_settings.txt"
    write_settings(GameLogic.Object['current_settingsfile'])
    fn_events = fn[:-4] + "_events"
    GameLogic.Object['event_file'] = open(fn_events, 'wb')

    sys.stdout.write("         %s\n" % GameLogic.Object['current_movfile'])
    sys.stdout.write("         %s\n" % GameLogic.Object['current_ephysfile'])
    # start ephys and video recording:
    if settings.has_webcam:
        gc.safe_send(GameLogic.Object['vidconn'], "begin%send" % GameLogic.Object['current_movfile'],
                  "BLENDER: Couldn't start video; resource unavailable\n")
    if GameLogic.Object['has_fw']:
        gc.safe_send(GameLogic.Object['fwconn'], "begin%send" % GameLogic.Object['current_fwfile'],
                  "BLENDER: Couldn't start video; resource unavailable\n")

    if settings.has_comedi and ncl.has_comedi:
        gc.safe_send(GameLogic.Object['comediconn'], "begin%send" % GameLogic.Object['current_ephysfile'],
                  "BLENDER: Couldn't start electrophysiology; resource unavailable\n")

        # Wait for comedi to initialize the channels before triggering
        datadec = ""
        while datadec.find('primed')==-1:
            try:
                data = GameLogic.Object['comediconn'].recv(1024)
                datadec = data.decode('latin-1')
                print(data)
            except:
                pass
        print("found")
        ncl.set_trig(outtrigch, 1)

        # get ephys start time:
        GameLogic.Object['ephysstart'] = (parse_ephystimes(GameLogic.Object['comediconn'])-GameLogic.Object['time0'])[0]
    else:
        # TODO: get correct intan ephys start time
        GameLogic.Object['ephysstart'] = time.time()-GameLogic.Object['time0']
        
    # Copy current settings:
    fn_settings_py = fn[:-4] + "_settings.py"
    blenderpath = GameLogic.expandPath('//')
    shutil.copyfile('%s/py/settings.py' % blenderpath, fn_settings_py)
    
def write_looming(circle):
    GameLogic.Object['current_loomfile'].write(np.array([
        circle.worldPosition[0],
        circle.worldPosition[1],
        circle.worldPosition[2],
        circle.localScale.x,
        circle.localScale.y,
        circle.localScale.z], dtype=np.float64).tobytes())
    GameLogic.Object['current_loomfile'].flush()