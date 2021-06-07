import sys
import numpy as np
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('GstBase', '1.0')
from gi.repository import Gst, GstApp, GstBase, GLib, GObject
import cairo
import time
import logging
from ctypes import *
import struct
import os
import datetime

import fit
from gst_hacks import map_gst_buffer

Gst.init(sys.argv)

FILE='/home/joshua/gopro/20210605-copperopolis/GX010029.MP4'
FRAMERATE=30000/1001
FITFILE='/home/joshua/gopro/20210605-copperopolis/Copperopolis_Road_Race_off_the_back_7_19_but_at_least_I_didn_t_DNF_.fit'
TIMEFUDGE=36.58
FLIP=True

# Load the timecode.  XXX: is there a better way to do this?
TMCD_OUT='tmp_tmcd'
os.system(f"ffmpeg -i {FILE} -map 0:d:0 -y -f data {TMCD_OUT}")
with open(TMCD_OUT, "rb") as f:
    tmcd_frames = struct.unpack(">I", f.read())[0]
tmcd_secs = tmcd_frames / FRAMERATE
print(tmcd_secs)
start_time = datetime.datetime(year = 2021, month = 6, day = 5) + datetime.timedelta(seconds = tmcd_secs) # this is LOCAL TIME

start_time += datetime.timedelta(hours = 7)
start_time += datetime.timedelta(seconds = -TIMEFUDGE)

f = fit.FitByTime(FITFILE)

def paint(ctx, w, h, tm):
    txt = f"{f.lerp_value(tm, 'heart_rate'):.1f} bpm, {f.lerp_value(tm, 'speed'):.1f} kph, {f.lerp_value(tm, 'cadence'):.1f} rpm"
    
    ctx.select_font_face("Ubuntu", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    fsz = h // 10
    ctx.set_font_size(fsz)

    ctx.set_source_rgba(0, 0, 0, 0.6)
    xp = w // 10
    yp = h - h // 10
    ctx.move_to(xp, yp)
    ctx.show_text(txt)
    
    ctx.set_source_rgba(0.9, 0.2, 0.2, 1.0)
    ctx.move_to(xp - fsz // 10, yp - fsz // 10)
    ctx.show_text(txt)

# https://github.com/jackersson/gst-overlay/blob/master/gst_overlay/gst_overlay_cairo.py
class GstOverlayGPS(GstBase.BaseTransform):
    __gstmetadata__ = ("GPS overlay object",
                       "video.py",
                       "GPS overlay",
                       "jwise")
    __gsttemplates__ = (Gst.PadTemplate.new("src",
                                            Gst.PadDirection.SRC,
                                            Gst.PadPresence.ALWAYS,
                                            Gst.Caps.from_string("video/x-raw,format=BGRA")),
                        Gst.PadTemplate.new("sink",
                                            Gst.PadDirection.SINK,
                                            Gst.PadPresence.ALWAYS,
                                            Gst.Caps.from_string("video/x-raw,format=BGRA")))
    def __init__(self):
        super(GstOverlayGPS, self).__init__()
    
    def do_transform_ip(self, buffer):
        print(f"transform! {self.segment.position / 1000000000}")
        caps = self.srcpad.get_current_caps()
        h = caps.get_structure(0).get_value("height")
        w = caps.get_structure(0).get_value("width")
        
        #
        #success, map_info = buffer.map(Gst.MapFlags.WRITE)
        #if not success:
        #    raise RuntimeError('failed to map buffer')
        
        #print(cast(map_info.data, c_void_p))
        #data = cast(map_info.data, POINTER(c_char * len(map_info.data)))[0]
        #print(type(map_info.data))
        #print(map_info.data[0:4])
        #print(data[0:4])
        with map_gst_buffer(buffer, Gst.MapFlags.READ) as data:
            surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h)
            ctx = cairo.Context(surf)
            paint(ctx, w, h, start_time + datetime.timedelta(seconds = self.segment.position / 1000000000))
        
        #buffer.unmap(map_info)
        
        return Gst.FlowReturn.OK


def register(plugin):
    return Gst.Element.register(plugin, 'gpsoverlay', 0, GObject.type_register(GstOverlayGPS))
if not Gst.Plugin.register_static(Gst.VERSION_MAJOR, Gst.VERSION_MINOR, 'gpsoverlay', 'GPS overlay object', register, '0.0', 'unknown', 'gstreamer', 'gpsrenda', 'the.internet'):
    raise ImportError("failed to register gpsoverlay with gstreamer")
                                                                                        
pipeline = Gst.parse_launch(
    f"filesrc location={FILE} ! decodebin name=decoder "
    f"decoder. ! queue ! audioconvert ! audioresample ! alsasink "
    f"decoder. ! videoconvert ! " +
    ("videoflip method=rotate-180 ! " if FLIP else "") +
    f"gpsoverlay ! videoconvert ! "
    f"autovideosink"
    )


loop = GLib.MainLoop()

def on_message(bus, message, loop):
    mtype = message.type
    print(mtype)
    if mtype == Gst.MessageType.EOS:
        print("EOS")
        loop.quit()
    elif mtype == Gst.MessageType.ERROR:
        print("Error!")
    elif mtype == Gst.MessageType.WARNING:
        print("Warning!")
    return True

bus = pipeline.get_bus()
bus.connect("message", on_message, None)

pipeline.set_state(Gst.State.PLAYING)
pipeline.seek_simple(Gst.Format.TIME,  Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 30 * Gst.SECOND) 

try:
    loop.run()
except:
    loop.quit()
