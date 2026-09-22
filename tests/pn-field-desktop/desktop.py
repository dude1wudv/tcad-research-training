#!/usr/bin/python
"""Guest X11 desktop capture/input; run as the logged-in tcad user, DISPLAY=:0."""
import argparse
import ctypes
import time

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['capture', 'type', 'click'])
parser.add_argument('value')
parser.add_argument('--window', type=lambda x: int(x, 0))
args = parser.parse_args()
if args.action == 'capture':
    import gi
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk
    root = Gdk.get_default_root_window()
    pixbuf = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
    pixbuf.savev(args.value, 'png', [], [])
else:
    x = ctypes.CDLL('libX11.so.6')
    xt = ctypes.CDLL('libXtst.so.6')
    x.XOpenDisplay.restype = ctypes.c_void_p
    x.XStringToKeysym.argtypes = [ctypes.c_char_p]
    x.XStringToKeysym.restype = ctypes.c_ulong
    x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    x.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x.XFlush.argtypes = [ctypes.c_void_p]
    xt.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    xt.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    xt.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
    display = x.XOpenDisplay(None)
    if not display:
        raise RuntimeError('No accessible X11 desktop')
    if args.window:
        x.XRaiseWindow(display, args.window)
        x.XSetInputFocus(display, args.window, 1, 0)
        x.XFlush(display)
        time.sleep(0.2)
    def key(name, down):
        code = x.XKeysymToKeycode(display, x.XStringToKeysym(name.encode('ascii')))
        if not code:
            raise ValueError('Unmapped key: ' + name)
        xt.XTestFakeKeyEvent(display, code, down, 0)
    if args.action == 'click':
        px, py = map(int, args.value.split(','))
        xt.XTestFakeMotionEvent(display, -1, px, py, 0)
        xt.XTestFakeButtonEvent(display, 1, 1, 0)
        xt.XTestFakeButtonEvent(display, 1, 0, 0)
    else:
        names = {'\n': 'Return', ' ': 'space', '-': 'minus', '/': 'slash', '.': 'period', '_': 'underscore', ':': 'colon'}
        for char in args.value:
            shifted = char.isupper() or char in '_:'
            if shifted:
                key('Shift_L', 1)
            name = names.get(char, char.lower())
            key(name, 1)
            key(name, 0)
            if shifted:
                key('Shift_L', 0)
            x.XFlush(display)
            time.sleep(0.03)
    x.XFlush(display)
