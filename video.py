import sys
import numpy as np
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('GstBase', '1.0')
from gi.repository import Gst, GstApp, GstBase, GLib, GObject
import cairo
import time
import struct
import os
import datetime

from gst_hacks import map_gst_buffer
import fit
from widgets import *

Gst.init(sys.argv)

# start
#FILE='/home/joshua/gopro/20210605-copperopolis/GX010026.MP4'
#SEEKTIME=140

# robin
#FILE='/home/joshua/gopro/20210605-copperopolis/GX010037.MP4'
#SEEKTIME=0

# descent
FILE='/home/joshua/gopro/20210605-copperopolis/GX010031.MP4'
SEEKTIME=0

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

cadence_gauge    = GaugeHorizontal(30, 1080 - 30 - 65 * 1, label = '{val:.0f}', caption = 'rpm', data_range = [(75, (1.0, 0, 0)), (90, (0.0, 0.6, 0.0)), (100, (0.0, 0.6, 0.0)), (120, (1.0, 0.0, 0.0))])
heart_rate_gauge = GaugeHorizontal(30, 1080 - 30 - 65 * 2, label = '{val:.0f}', caption = 'bpm', data_range = [(120, (0, 0.6, 0)), (150, (0.2, 0.6, 0.0)), (180, (0.8, 0.0, 0.0))])
speed_gauge      = GaugeHorizontal(30, 1080 - 30 - 65 * 3, label = '{val:.1f}', caption = 'mph', data_range = [(8, (0.6, 0, 0)), (15, (0.0, 0.6, 0.0)), (30, (1.0, 0.0, 0.0))])
temp_gauge       = GaugeVertical  (1920 - 120, 30, data_range = [(60, (0.6, 0.6, 0.0)), (80, (0.6, 0.3, 0)), (100, (0.8, 0.0, 0.0))])
dist_total_mi    = f.fields['distance'][-1][1] * 0.62137119
dist_gauge       = GaugeHorizontal(30, 30, w = 1920 - 120 - 30 - 30, label = "{val:.1f}", dummy_label = "99.9", caption = f" / {dist_total_mi:.1f} miles", dummy_caption = None, data_range = [(0, (0.8, 0.7, 0.7)), (dist_total_mi, (0.7, 0.8, 0.7))])
map              = GaugeMap(1920 - 30 - 400, 1080 - 30 - 65 * 3, h = 65 * 3)
elevmap          = GaugeElevationMap(1920 - 30 - 400 - 30 - 400, 1080 - 30 - 65 * 3, h = 65 * 3)
map.prerender(f.fields['position_lat'], f.fields['position_long'])
elevmap.prerender(f.fields['distance'], f.fields['altitude'])

def paint(ctx, w, h, tm):
    cadence = f.lerp_value(tm, 'cadence', flatten_zeroes = datetime.timedelta(seconds = 2.0))
    cadence_gauge.render(ctx, cadence)
    
    heart_rate = f.lerp_value(tm, 'heart_rate')
    heart_rate_gauge.render(ctx, heart_rate)
    
    speed_kph = f.lerp_value(tm, 'speed')
    speed_mph = speed_kph * 0.62137119 if speed_kph is not None else None
    speed_gauge.render(ctx, speed_mph)
    
    temp_c = f.lerp_value(tm, 'temperature')
    temp_f = (temp_c * 9 / 5) + 32 if temp_c is not None else None
    temp_gauge.render(ctx, temp_f)
    
    dist_km = f.lerp_value(tm, 'distance')
    dist_mi = dist_km * 0.62137119 if dist_km is not None else None
    dist_gauge.render(ctx, dist_mi)
    
    latitude  = f.lerp_value(tm, 'position_lat')
    longitude = f.lerp_value(tm, 'position_long')
    map.render(ctx, latitude, longitude)
    
    altitude = f.lerp_value(tm, 'altitude')
    grade    = f.lerp_value(tm, 'grade')
    elevmap.render(ctx, dist_km, altitude, grade)

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
        tst = time.time()
        caps = self.srcpad.get_current_caps()
        h = caps.get_structure(0).get_value("height")
        w = caps.get_structure(0).get_value("width")
        
        with map_gst_buffer(buffer, Gst.MapFlags.READ) as data:
            surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h)
            ctx = cairo.Context(surf)
            paint(ctx, w, h, start_time + datetime.timedelta(seconds = self.segment.position / 1000000000))
        
        print(f"transform took {(time.time() - tst) * 1000:.1f}ms")
        
        return Gst.FlowReturn.OK


def register(plugin):
    return Gst.Element.register(plugin, 'gpsoverlay', 0, GObject.type_register(GstOverlayGPS))
if not Gst.Plugin.register_static(Gst.VERSION_MAJOR, Gst.VERSION_MINOR, 'gpsoverlay', 'GPS overlay object', register, '0.0', 'unknown', 'gstreamer', 'gpsrenda', 'the.internet'):
    raise ImportError("failed to register gpsoverlay with gstreamer")

pipeline = Gst.parse_launch(
    f"filesrc location={FILE} ! decodebin name=decoder "
    f"decoder. ! queue ! audioconvert ! audioresample ! alsasink "
    f"decoder. ! queue ! videoconvert ! " +
    ("videoflip method=rotate-180 ! " if FLIP else "") +
    f"gpsoverlay ! videoconvert ! queue ! "
    f"autovideosink"
    )


loop = GLib.MainLoop()

did_seek = False

def on_message(bus, message, pipeline, loop):
    global did_seek
    
    mtype = message.type
    if mtype == Gst.MessageType.STATE_CHANGED:
        old_state, new_state, pending_state = message.parse_state_changed()
        print(f"pipeline state: {Gst.Element.state_get_name(old_state)} -> {Gst.Element.state_get_name(new_state)}")
        
        if new_state == Gst.State.PLAYING:
            q = Gst.Query.new_seeking(Gst.Format.TIME)
            pipeline.query(q)
            fmt, seek_enabled, start, end = q.parse_seeking()
            print(f"seek_enabled {seek_enabled}")
            
            if not did_seek:
                pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, SEEKTIME * Gst.SECOND) 
                did_seek = True

    if mtype == Gst.MessageType.EOS:
        print("EOS")
        loop.quit()
    elif mtype == Gst.MessageType.ERROR:
        print("Error!")
    elif mtype == Gst.MessageType.WARNING:
        print("Warning!")
    else:
        print(mtype)
    return True

bus = pipeline.get_bus()
bus.connect("message", on_message, pipeline, loop)
bus.add_signal_watch()

pipeline.set_state(Gst.State.PLAYING)
pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 30 * Gst.SECOND) 

try:
    loop.run()
except:
    loop.quit()
