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

    if len(mice):
        s1, conn1, addr1, p1 = \
            gu.spawn_process("\0mouse0socket", 
                          ['%s/evread/readout' % blenderpath, '%d' % mice[0].evno, '0'])
        s2, conn2, addr2, p2 = \
            gu.spawn_process("\0mouse1socket", 
                          ['%s/evread/readout' % blenderpath, '%d' % mice[2].evno, '1'])

        conn1.send(b'start')
        conn2.send(b'start')

        gu.recv_ready(conn1)
        gu.recv_ready(conn2)

        conn1.setblocking(0)
        conn2.setblocking(0)

        GameLogic.Object['m1conn'] = conn1
        GameLogic.Object['m2conn'] = conn2

    else:
        GameLogic.Object['m1conn'] = None
        GameLogic.Object['m2conn'] = None

conn1 = GameLogic.Object['m1conn']
conn2 = GameLogic.Object['m2conn']

# define main program
def main():
    if GameLogic.Object['closed']:
        return

    # get controller
    controller = GameLogic.getCurrentController()
    gu.keep_conn([conn1, conn2]) 

    if conn1 is not None:
        # get mouse movement
        t1, dt1, x1, y1 = gu.read32(conn1)
        t2, dt2, x2, y2 = gu.read32(conn2)
    else:
        t1, dt1, x1, y1 = np.array([0,]), np.array([0,]), np.array([0,]), np.array([0,])
        t2, dt2, x2, y2 = np.array([0,]), np.array([0,]), np.array([0,]), np.array([0,])
    
    # move according to ball readout:
    movement(controller, (x1, y1, x2, y2, t1, t2, dt1, dt2))

# define useMouseLook
def movement(controller, move):

    # Note that x is mirrored if the dome projection is used.
    xtranslate = 0 #
    ytranslate = 0
    zrotate = 0
    gain = 1e-3

    # Simple example how the mice could be read out

    # y axis front mouse
    if len(move[3]):
        # pass
        ytranslate = float(move[3].sum()) * gain
    # x axis front mouse / side mouse
    if len(move[0]) and len(move[2]):
        # pass
        zrotate = float(move[0].sum()+move[2].sum())/2.0 * gain

    # y axis side mouse
    if len(move[1]):
        zrotate += float((move[1].sum()))*gain
        
    # Get the actuators
    act_xtranslate = controller.actuators["xtranslate"]
    act_ytranslate = controller.actuators["ytranslate"]
    act_zrotate    = controller.actuators["zrotate"]

    act_ytranslate.dLoc = [xtranslate, ytranslate, 0.0]
    act_ytranslate.useLocalDLoc = True

    act_zrotate.dRot = [0.0, 0.0, zrotate]
    act_zrotate.useLocalDRot = False

    # Use the actuators 
    controller.activate(act_xtranslate)
    controller.activate(act_zrotate)
    controller.activate(act_ytranslate)

main()
