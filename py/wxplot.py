"""
This demo demonstrates how to draw a dynamic mpl (matplotlib) 
plot in a wxPython application.

It allows "live" plotting as well as manual zooming to specific
regions.

Both X and Y axes allow "auto" or "manual" settings. For Y, auto
mode sets the scaling of the graph to see all the data points.
For X, auto mode makes the graph "follow" the data. Set it X min
to manual 0 to always see the whole data from the beginning.

Note: press Enter in the 'manual' text box to make a new value 
affect the plot.

Eli Bendersky (eliben@gmail.com)
License: this code is in the public domain
Last modified: 31.07.2008

Retrieved from 
http://eli.thegreenplace.net/files/prog_code/wx_mpl_dynamic_graph.py.txt

Modified by C. Schmidt-Hieber <christsc@gmx.de> as a scope
for Gnoom.

Last modified: 05.02.2011
"""
import os
import sys
import socket
import string
import time
import wxversion
wxversion.select('2.8')
import wx

# The recommended way to use wx with mpl is with the WXAgg
# backend. 
#
import matplotlib
matplotlib.use('WX')
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import \
    FigureCanvasWxAgg as FigCanvas, \
    NavigationToolbar2WxAgg as NavigationToolbar
import numpy as np
import pylab

def init_socket(sockname):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connected = False
    while not connected:
        try:
            s.connect(sockname)
            connected=True
        except:
            pass
            # sys.stdout.write("WXPLOT: Couldn't connect to socket %s. Will retry...\n" % sockname)

    try:
        blenderpath = (s.recv(1024)).decode('latin-1')
        s.send(b'ready')
    except:
        pass
        # sys.stdout.write("WXPLOT: Didn't receive data.\n")

    s.setblocking(0)

    return s, blenderpath, connected

class GraphFrame(wx.Frame):
    """ The main frame of the application
    """
    title = 'Comedi Scope'
    
    def __init__(self, dt, sockno):
        wx.Frame.__init__(self, None, -1, self.title, (1280,0))
        
        self.dt = dt
        self.tinterval = 50.0e-3
        self.plotsize = 1000.0e-3
        self.rectime = 0.0
        self.dataIC = np.array([0,0])
        self.dataFR = np.array([0,0])
        self.dataEC = np.array([0,0])
        self.sockic, self.blenderpath, self.connected = init_socket("\0icsocket%d" % sockno)
        self.sockec, self.blenderpath, self.connected = init_socket("\0ecsocket%d" % sockno)
        self.sockfr, self.blenderpath, self.connected = init_socket("\0frsocket%d" % sockno)
        self.t_disconnect = time.time()
        self.create_main_panel()
        
        self.redraw_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_redraw_timer, self.redraw_timer)        
        self.redraw_timer.Start(self.tinterval * 1e3)

        self.draw_plot()

    def create_main_panel(self):
        self.panel = wx.Panel(self)

        self.init_plot()
        self.canvas = FigCanvas(self.panel, -1, self.fig)
                                        
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        self.vbox.Add(self.canvas, 1, flag=wx.LEFT | wx.TOP | wx.GROW)        
        
        self.panel.SetSizer(self.vbox)
        self.vbox.Fit(self)
    
    def init_plot(self):
        self.dpi = 75
        self.fig = Figure((8.0, 9.0), dpi=self.dpi)

        self.axesIC = self.fig.add_subplot(311)
        self.axesIC.set_axis_bgcolor('black')
        pylab.setp(self.axesIC.get_xticklabels(), fontsize=10)
        pylab.setp(self.axesIC.get_yticklabels(), fontsize=10)

        # plot the data as a line series, and save the reference 
        # to the plotted line series
        self.plot_dataIC = self.axesIC.plot(
            np.arange(len(self.dataFR))*self.dt, self.dataIC, 
            linewidth=1,
            color=(1, 1, 0),
            )[0]
        xmax = self.plotsize + self.tinterval*5.0
        xmin = 0
        self.axesIC.set_xbound(lower=xmin, upper=xmax)
        self.axesIC.grid(True, color='gray')

        self.axesEC = self.fig.add_subplot(312, sharex=self.axesIC)
        self.axesEC.set_axis_bgcolor('black')
        pylab.setp(self.axesEC.get_xticklabels(), fontsize=10)
        pylab.setp(self.axesEC.get_yticklabels(), fontsize=10)

        # plot the data as a line series, and save the reference 
        # to the plotted line series
        self.plot_dataEC = self.axesEC.plot(
            np.arange(len(self.dataEC))*self.dt, self.dataEC, 
            linewidth=1,
            color=(1, 1, 0),
            )[0]
        xmax = self.plotsize + self.tinterval*5.0
        xmin = 0
        self.axesEC.set_xbound(lower=xmin, upper=xmax)
        self.axesEC.grid(True, color='gray')

        self.axesFR = self.fig.add_subplot(313, sharex=self.axesIC)
        self.axesFR.set_axis_bgcolor('black')
        self.axesFR.set_xlabel('Time (s)', size=12)
        pylab.setp(self.axesFR.get_xticklabels(), fontsize=10)
        pylab.setp(self.axesFR.get_yticklabels(), fontsize=10)

        # plot the data as a line series, and save the reference 
        # to the plotted line series
        self.plot_dataFR = self.axesFR.plot(
            np.arange(len(self.dataFR))*self.dt, self.dataFR, 
            linewidth=1,
            color=(1, 1, 0),
            )[0]
        xmax = self.plotsize + self.tinterval*5.0
        xmin = 0
        self.axesFR.set_ybound(lower=-0.1, upper=1.1)
        self.axesFR.set_xbound(lower=xmin, upper=xmax)
        self.axesFR.grid(True, color='gray')

    def draw_plot(self):
        """ Redraws the plot
        """
        self.plot_dataIC.set_xdata(np.arange(len(self.dataIC))*self.dt + self.rectime)
        self.plot_dataIC.set_ydata(np.array(self.dataIC))

        self.plot_dataEC.set_xdata(np.arange(len(self.dataEC))*self.dt + self.rectime)
        self.plot_dataEC.set_ydata(np.array(self.dataEC))

        self.plot_dataFR.set_xdata(np.arange(len(self.dataFR))*self.dt + self.rectime)
        self.plot_dataFR.set_ydata(np.array(self.dataFR))
        
        self.canvas.draw()
    
    def on_redraw_timer(self, event):
        reset = False
        replot = False
        if len(self.dataIC) > self.plotsize/self.dt:
            reset = True
        datadec = ""
        try:
            data = self.sockic.recv(32768)
            datadec = data.decode('latin-1')
            has_data = True
        except:
            has_data = False
        if has_data and datadec.find('quit') != -1:
            sys.stdout.write("WXPLOT: Received termination signal... ")
            sys.stdout.flush()
            self.fig.clear()
            self.sockic.send(b"close")
            self.sockic.close()
            self.sockec.close()
            self.sockfr.close()
            self.Destroy()
            sys.exit(0)
        elif has_data and datadec.find('begin') != -1:
            self.rectime = 0
            sys.stdout.write("WXPLOT: Starting new plot\n")
        elif has_data and datadec.find('alive')==-1 and len(data)>0:
            tmpIC = np.fromstring(data, dtype=np.float32)
            if reset:
                self.rectime += len(self.dataIC) * self.dt
                self.dataIC = np.empty((0))
            self.dataIC = np.concatenate([self.dataIC, tmpIC])
            if reset:
                xmin = self.rectime
                xmax = self.rectime + self.plotsize + self.tinterval*5.0
                ymin = np.min(self.dataIC)
                ymax = np.max(self.dataIC)
                amp = ymax-ymin
                self.axesIC.set_xbound(lower=xmin, upper=xmax)
                self.axesIC.set_ybound(lower=ymin-0.5*amp, upper=ymax+0.5*amp)
            replot = True

        reset = False
        if len(self.dataEC) > self.plotsize/self.dt:
            self.dataEC = np.empty((0))
            reset = True
        try:
            dataec = self.sockec.recv(32768)
            has_dataec = True
        except:
            has_dataec = False

        if has_dataec and len(dataec)>0:
            tmpEC = np.fromstring(dataec, dtype=np.float32)
            self.dataEC = np.concatenate([self.dataEC, tmpEC])
            if reset:
                xmin = self.rectime
                xmax = self.rectime + self.plotsize + self.tinterval*5.0
                ymin = np.min(self.dataEC)
                ymax = np.max(self.dataEC)
                amp = ymax-ymin
                self.axesEC.set_xbound(lower=xmin, upper=xmax)
                self.axesEC.set_ybound(lower=ymin-0.5*amp, upper=ymax+0.5*amp)

        reset = False
        if len(self.dataFR) > self.plotsize/self.dt:
            self.dataFR = np.empty((0))
            reset = True
        try:
            datafr = self.sockfr.recv(32768)
            has_datafr = True
        except:
            has_datafr = False

        if has_datafr and len(datafr)>0:
            tmpFR = np.fromstring(datafr, dtype=np.int8)
            self.dataFR = np.concatenate([self.dataFR, tmpFR])
            if reset:
                xmin = self.rectime
                xmax = self.rectime + self.plotsize + self.tinterval*5.0
                self.axesFR.set_xbound(lower=xmin, upper=xmax)

        if replot:
            self.draw_plot()
        else:
            time.sleep(1e-4)

class GraphApp(wx.PySimpleApp):

    def __init__(self):
        wx.PySimpleApp.__init__(self, redirect=False, filename=None, useBestVisual=False, clearSigInt=True) 

if __name__ == '__main__':
    # parse arguments:
    dt = 0.02
    if len(sys.argv) > 1:
        dt = float(sys.argv[1]) * 1e-6 # convert to s
    if len(sys.argv) > 2:
	    sockno = int(sys.argv[2])
    else:
        sockno = 0
    sys.stdout.write("WXPLOT: dt is %f s\n" % dt)
    app = GraphApp()
    app.frame = GraphFrame(dt, sockno)
    app.frame.Show()
    app.MainLoop()
    sys.stdout.write("WXPLOT: mainloop done\n")
