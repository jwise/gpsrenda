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
import colorsys

import fit
from gst_hacks import map_gst_buffer

Gst.init(sys.argv)

FILE='/home/joshua/gopro/20210605-copperopolis/GX010035.MP4'
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

def lerp(x0, v0, x1, v1, x):
    if x < x0:
        return v0
    if x > x1:
        return v1
    alpha = (x - x0) / (x1 - x0)
    return v0 * (1.0 - alpha) + v1 * alpha

class GaugeHorizontal:
    def __init__(self, x, y, w = 600, h = 60, label = '{val:.0f}', caption = '', data_range = [(0, (1.0, 0, 0)), (100, (1.0, 0, 0))]):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.label = label
        self.caption = caption
        
        self.padding = h / 8
        self.textw = h * 3.2
        self.gaugew = self.w - self.textw - self.padding
        
        self.min = data_range[0][0]
        self.max = data_range[-1][0]
        
        self.data_range = data_range
        
        # Cairo does not have a HSV gradient, so we make our own to
        # interpolate the colors of the gauge.
        self.pattern = cairo.LinearGradient(self.x, 0, self.x + self.gaugew, 0)
        self.pattern.add_color_stop_rgb(0.0, data_range[0][1][0], data_range[0][1][1], data_range[0][1][2])
        last = (0.0, data_range[0][1])
        for v in data_range[1:]:
            last_hsv = colorsys.rgb_to_hsv(*last[1])
            this_hsv = colorsys.rgb_to_hsv(*v[1])
            v = (lerp(self.min, 0.0, self.max, 1.0, v[0]), v[1])

            SUBSTOPS = 20
            for p in range(SUBSTOPS):
                # This is hokey, and does not interpolate 'the short way'
                # around the hue circle.  But it does interpolate correctly
                # from red to green, so ...
                rgb = colorsys.hsv_to_rgb(lerp(0, last_hsv[0], SUBSTOPS - 1, this_hsv[0], p),
                                          lerp(0, last_hsv[1], SUBSTOPS - 1, this_hsv[1], p),
                                          lerp(0, last_hsv[2], SUBSTOPS - 1, this_hsv[2], p))
                self.pattern.add_color_stop_rgb(lerp(0, last[0], SUBSTOPS - 1, v[0], p), rgb[0], rgb[1], rgb[2])
            
            last = v
        
        self.bgpattern = cairo.LinearGradient(0, self.y, 0, self.y + self.h)
        self.bgpattern.add_color_stop_rgba(0.0, 0.2, 0.2, 0.2, 0.9)
        self.bgpattern.add_color_stop_rgba(1.0, 0.4, 0.4, 0.4, 0.9)
    
    def render(self, ctx, val):
        if val is None:
            ctx.push_group()
            ctx.rectangle(self.x, self.y, self.w, self.h)
            ctx.set_source(self.bgpattern)
            ctx.fill()
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(0.9)
            return
        
        ctx.select_font_face("Ubuntu", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(self.h * 0.9)
        
        ctx.push_group()
        
        # paint a background
        ctx.rectangle(self.x, self.y, self.w, self.h)
        ctx.set_source(self.bgpattern)
        ctx.fill()
        
        # paint the gauge bar itself
        ctx.rectangle(self.x + self.padding, self.y + self.padding, lerp(self.min, 0, self.max, self.gaugew, val), self.h - self.padding * 2)
        ctx.set_source(self.pattern)
        ctx.fill()

        # grumble: there's no easy way to look up a point in a pattern.  but
        # we want to know the current color!  at least it is slightly easier
        # than the HSV shenanigans above...
        last = self.data_range[0]
        this = self.data_range[0]
        for this in self.data_range[1:]:
            if this[0] >= val:
                break
            last = this
        last_hsv = colorsys.rgb_to_hsv(*last[1])
        this_hsv = colorsys.rgb_to_hsv(*this[1])
        cur_hsv = (lerp(last[0], last_hsv[0], this[0], this_hsv[0], val),
                   lerp(last[0], last_hsv[1], this[0], this_hsv[1], val),
                   lerp(last[0], last_hsv[2], this[0], this_hsv[2], val))
        cur_rgb = colorsys.hsv_to_rgb(*cur_hsv)
        
        # paint a semitransparent overlay on the gauge bar to colorize it
        # for where we are in the scale
        ctx.rectangle(self.x + self.padding, self.y + self.padding, lerp(self.min, 0, self.max, self.gaugew, val), self.h - self.padding * 2)
        ctx.set_source_rgba(cur_rgb[0], cur_rgb[1], cur_rgb[2], 0.4)
        ctx.fill()

        # paint the surround for the gauge cluster
        ctx.rectangle(self.x + self.padding, self.y + self.padding, self.gaugew, self.h - self.padding * 2)
        ctx.set_line_width(4)
        ctx.set_source_rgb(0, 0, 0)
        ctx.stroke()
        
        # render the big numbers
        text = self.label.format(val = val)
        
        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(self.x + self.gaugew + self.padding * 2 + self.h * 0.1, self.y + self.h - self.padding)
        ctx.show_text(text)

        ctx.set_source_rgb(*colorsys.hsv_to_rgb(cur_hsv[0], 0.1, 1.0))
        ctx.move_to(self.x + self.gaugew + self.padding * 2, self.y + self.h - self.h * 0.1 - self.padding)
        ctx.show_text(text)

        # render the caption
        ctx.set_font_size(self.h * 0.5)

        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(self.x + self.w - self.h * 1.2 + self.h * 0.1, self.y + self.h - self.padding)
        ctx.show_text(self.caption)

        ctx.set_source_rgb(1, 1, 1)
        ctx.move_to(self.x + self.w - self.h * 1.2,                self.y + self.h - self.h * 0.1 - self.padding)
        ctx.show_text(self.caption)
        
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(0.9)

cadence_gauge    = GaugeHorizontal(30, 1080 - 30 - 65 * 1, label = '{val:.0f}', caption = 'rpm', data_range = [(75, (1.0, 0, 0)), (90, (0.0, 0.6, 0.0)), (100, (0.0, 0.6, 0.0)), (120, (1.0, 0.0, 0.0))])
heart_rate_gauge = GaugeHorizontal(30, 1080 - 30 - 65 * 2, label = '{val:.0f}', caption = 'bpm', data_range = [(120, (0, 0.6, 0)), (150, (0.2, 0.6, 0.0)), (180, (0.8, 0.0, 0.0))])
speed_gauge      = GaugeHorizontal(30, 1080 - 30 - 65 * 3, label = '{val:.1f}', caption = 'mph', data_range = [(8, (0.6, 0, 0)), (15, (0.0, 0.6, 0.0)), (30, (1.0, 0.0, 0.0))])

def paint(ctx, w, h, tm):
    cadence = f.lerp_value(tm, 'cadence', flatten_zeroes = datetime.timedelta(seconds = 2.0))
    cadence_gauge.render(ctx, cadence)
    
    heart_rate = f.lerp_value(tm, 'heart_rate')
    heart_rate_gauge.render(ctx, heart_rate)
    
    speed_kph = f.lerp_value(tm, 'speed')
    speed_mph = speed_kph * 0.62137119 if speed_kph is not None else None
    speed_gauge.render(ctx, speed_mph)

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
