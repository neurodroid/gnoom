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

# Use xinput utility to soft detach mice
# (c) C. Schmidt-Hieber, 2013

import subprocess as sp
import string
import os
import sys

py3 = (sys.version_info[0] >= 3)

class event_mouse(object):
    def __init__(self, evno, id):
        self.evno = evno
        self.id = id

        if py3:
            out = str(sp.Popen(['xinput', 'list-props', '%d' % self.id], stdout=sp.PIPE).communicate()[0], encoding='latin-1')
        else:
            out = sp.Popen(['xinput', 'list-props', '%d' % self.id], stdout=sp.PIPE).communicate()[0]
            
        for line in out.split('\n'):
            if 'Device Enabled' in line:
                if py3:
                    self.enable_code = int(line[line.find('(')+1:\
                                                    line.find(')')])
                else:
                    self.enable_code = int(line[string.find(line, '(')+1:\
                                                    string.find(line, ')')])
                break

def find_mice(model="Kone"):
    if py3:
        out = str(sp.Popen(['xinput', 'list'], stdout=sp.PIPE).communicate()[0], encoding='latin-1')
        ids = [int(line[line.find("id=")+3:line.find("id=")+5]) \
                   for line in out.split('\n') if model in line]    
    else:
        out = sp.Popen(['xinput', 'list'], stdout=sp.PIPE).communicate()[0]
        ids = [int(line[string.find(line, "id=")+3:string.find(line, "id=")+5]) \
                   for line in string.split(out, '\n') if model in line]

    ids.sort()

    devno = 0
    mice = []
    nid = 0
    while os.path.exists("/sys/class/input/event%d" % devno):
        devname = open("/sys/class/input/event%d/device/name" % devno).read()

        if model in devname:
            sys.stdout.write("Found on event%d\n" % (devno))
            try:
                mice.append(event_mouse(devno, ids[nid]))
            except:
                sys.stderr.write("Failed to add event%d\n" % (devno))
                
            nid += 1
        devno += 1

    return mice

def switch_mode(mouse, on=False):
    cmd = ['xinput', 'set-int-prop', '%d' % mouse.id, '%d' % mouse.enable_code, '8', '%d' % int(on)]
    proc = sp.Popen(cmd)

def set_owner(mouse):
    cmd = ['chmod', '+rw', '/dev/input/event%d' % mouse.evno]
    proc = sp.Popen(cmd)
    
if __name__=="__main__":
    mice = find_mice("G500")
    for mouse in mice:
        switch_mode(mouse, on=False)
