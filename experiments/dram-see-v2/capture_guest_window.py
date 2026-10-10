#!/usr/bin/python
"""Capture only an owned SVisual process tree's actual X11 application window."""
import argparse,ctypes,os,time
import gi
gi.require_version('Gdk','3.0')
gi.require_version('GdkX11','3.0')
from gi.repository import Gdk,GdkX11
p=argparse.ArgumentParser();p.add_argument('pid',type=int);p.add_argument('output');a=p.parse_args()
owned={a.pid}
for _ in range(8):
    for n in os.listdir('/proc'):
        if not n.isdigit():continue
        try:
            text=open('/proc/'+n+'/status').read()
            parent=int(next(t.split()[1] for t in text.splitlines() if t.startswith('PPid:')))
            if parent in owned:owned.add(int(n))
        except (IOError,StopIteration,ValueError):pass
x=ctypes.CDLL('libX11.so.6');x.XOpenDisplay.restype=ctypes.c_void_p
display=x.XOpenDisplay(None)
if not display:raise RuntimeError('No accessible X11 session')
x.XDefaultRootWindow.argtypes=[ctypes.c_void_p];x.XDefaultRootWindow.restype=ctypes.c_ulong
root=x.XDefaultRootWindow(display)
x.XInternAtom.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_int];x.XInternAtom.restype=ctypes.c_ulong
x.XGetWindowProperty.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_long,ctypes.c_long,ctypes.c_int,ctypes.c_ulong,
 ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_void_p)]
x.XFree.argtypes=[ctypes.c_void_p]
def prop(window,name):
    actual=ctypes.c_ulong();fmt=ctypes.c_int();count=ctypes.c_ulong();after=ctypes.c_ulong();data=ctypes.c_void_p()
    rc=x.XGetWindowProperty(display,window,x.XInternAtom(display,name.encode(),0),0,4096,0,0,
         ctypes.byref(actual),ctypes.byref(fmt),ctypes.byref(count),ctypes.byref(after),ctypes.byref(data))
    result=[]
    if rc==0 and data.value and fmt.value==32:
        values=ctypes.cast(data,ctypes.POINTER(ctypes.c_ulong));result=[values[i] for i in range(count.value)]
    if data.value:x.XFree(data)
    return result
clients=prop(root,'_NET_CLIENT_LIST');windows=[]
for wid in clients:
    pid=prop(wid,'_NET_WM_PID')
    if pid and pid[0] in owned:
        win=GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(),wid)
        if win and win.get_width()>300 and win.get_height()>200:windows.append((win.get_width()*win.get_height(),wid,win,pid[0]))
if not windows:raise RuntimeError('No owned mapped SVisual window; do not capture the unrelated desktop')
_,wid,win,pid=max(windows,key=lambda t:t[0])
x.XRaiseWindow.argtypes=[ctypes.c_void_p,ctypes.c_ulong];x.XFlush.argtypes=[ctypes.c_void_p]
x.XRaiseWindow(display,wid);x.XFlush(display);time.sleep(.8)
pix=Gdk.pixbuf_get_from_window(win,0,0,win.get_width(),win.get_height())
if pix is None:raise RuntimeError('Actual window pixels unavailable')
pix.savev(a.output,'png',[],[])
print('OWNED_WINDOW_CAPTURE pid=%s window=%s width=%s height=%s'%(pid,hex(wid),win.get_width(),win.get_height()))
