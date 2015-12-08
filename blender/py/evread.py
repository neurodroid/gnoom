# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# Read out mice from Blender
# (c) C. Schmidt-Hieber, 2013

from __future__ import print_function

import GameLogic
# first pass?
try:
    GameLogic.Object
    init = 0
except:
    init = 1

import sys
try:
    import numpy as np
except ImportError:
    # Add system Python path (required for Blender from ubuntu repositories):
    sys.path.append("/usr/lib/python%d.%d/site-packages" % (
            sys.version_info.major, sys.version_info.minor))
    sys.path.append("/usr/lib/python%d.%d/dist-packages" % (
            sys.version_info.major, sys.version_info.minor))
    import numpy as np

import xinput
import gnoomutils as gu

if init:
    GameLogic.Object = {}
    print("BLENDER: GameLogic object created")
    GameLogic.Object['closed'] = False

    GameLogic.setLogicTicRate(100)

    mice = xinput.find_mice(model="G500")
    for mouse in mice:
        # xinput.set_owner(mouse) # Don't need this if using correct udev rule
        xinput.switch_mode(mouse)

    blenderpath = GameLogic.expandPath('//')

    for mouseno in range(0, len(mice), 2):
        s1, conn1, addr1, p1 = \
            gu.spawn_process("\0mouse%dsocket" % int(mouseno/2), 
                          ['%s/evread/readout' % blenderpath, '%d' % mice[mouseno].evno, '%d' % (mouseno/2)])
        
        conn1.send(b'start')

        gu.recv_ready(conn1)

        conn1.setblocking(0)

        GameLogic.Object['m%dconn' % (int(mouseno/2) + 1)] = conn1

# define main program
def main():
    if GameLogic.Object['closed']:
        return

    # get controller
    controller = GameLogic.getCurrentController()

    nmouse = 1
    mkey = 'm%dconn' % (nmouse) 
    if mkey in GameLogic.Object.keys():
        t1, dt1, x1, y1 = gu.read32(GameLogic.Object[mkey])
        gu.keep_conn([GameLogic.Object[mkey]])
    else:
        t1, dt1, x1, y1 = 0, 0, np.array([0,]), np.array([0,])
    nmouse = 2
    mkey = 'm%dconn' % (nmouse) 
    if mkey in GameLogic.Object.keys():
        t2, dt2, x2, y2 = gu.read32(GameLogic.Object[mkey])
        gu.keep_conn([GameLogic.Object[mkey]])
    else:
        t2, dt2, x2, y2 = 0, 0, np.array([0,]), np.array([0,])

    
    # move according to ball readout:
    movement(controller, (x1, y1, x2, y2, t1, t2, dt1, dt2))

# define useMouseLook
def movement(controller, move):

    mouse_id_y_translate = 1
    mouse_id_z_rotate1 = 0
    mouse_id_z_rotate2 = 2
   
    # Note that x is mirrored if the dome projection is used.
    xtranslate = 0 #
    ytranslate = 0
    zrotate = 0
    gain = 1e-3

    # Simple example how the mice could be read out

    # y axis front mouse
    if len(move[mouse_id_y_translate]):
        # pass
        ytranslate = float(move[mouse_id_y_translate].sum()) * gain
    # x axis front mouse / side mouse
    if len(move[mouse_id_z_rotate1]):
        # pass
        zrotate = float(move[mouse_id_z_rotate1].sum()) * gain

    # y axis side mouse
    if len(move[mouse_id_z_rotate2]):
        zrotate += float((move[mouse_id_z_rotate2].sum()))*gain
    
    # get object that controller is attached to
    camera = controller.owner
    
    # set amount to move
    translation = [ xtranslate, ytranslate, 0]
    rotation = [0, 0, zrotate]
    
    # use local axis
    local = True

    # move game object
    camera.applyMovement(translation, local)
    camera.applyMovement(rotation, local)

main()
