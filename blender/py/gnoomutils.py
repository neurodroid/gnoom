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

# Some utilities for GNOOM
# (c) C. Schmidt-Hieber, 2013

import sys
import os
import socket
import subprocess
import time
import numpy as np

def keep_conn(connlist):
    for conn in connlist:
        if conn is not None:
            try:
                conn.send(b'1')
            except:
                sys.stdout.write("BLENDER: Couldn't send signal, will retry...\n")

def read32(conn):

    data1 = b''
    while True:
        try:
            data1 += conn.recv(32)
        except:
            break
    if len(data1):
        datanp = np.fromstring(data1, np.float64)
        t = datanp[::4]
        dt = datanp[1::4]
        y = datanp[2::4]
        x = datanp[3::4]
    else:
        t, dt, x, y = np.array([time.time()]),np.array([0]),np.array([0]),np.array([0])

    return t,dt,x,y

def recv_ready(conn):
    datadec = ""
    start = time.time()
    while datadec != 'ready':
       try:
          data = conn.recv(1024)
          datadec = data.decode('latin-1')
       except:
          if time.time()-start > 5000:
              return False
    return True

def spawn_process(procname, cmd='', shell=False, system=False, start=True, addenv=None):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    screated = False
    ntry = 0
    sprocname = procname
    if addenv is not None:
        env = dict(os.environ)
        env.update(addenv)
    else:
        env=None
        
    while not screated:
        procname = sprocname + "%d" % ntry
        sys.stdout.write("BLENDER: Trying new socket name %s\n" % procname)
        ntry += 1
        try:
            s.bind(procname)
            screated = True
        except:
            pass

    cmd.extend([('%d' % (ntry-1)),])
    if start:
        if not system:
            proc = subprocess.Popen(cmd, shell=shell, bufsize=-1, env=env)
        else:
            print("BLENDER: Executing", cmd)
            proc = os.system(" ".join(cmd))
    else:
        proc=None
    s.listen(1)
    conn, addr = s.accept()
    return s, conn, addr, proc

