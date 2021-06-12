import sys
import numpy as np
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('GstBase', '1.0')
from gi.repository import Gst, GstApp, GstBase, GLib, GObject
import time
import struct
import os
import datetime
import tempfile
import cairo

from gst_hacks import map_gst_buffer
import fit
from widgets import *

Gst.init(sys.argv)

# start
#FILE='/home/joshua/gopro/20210605-copperopolis/GX010026.MP4'
#SEEKTIME=140

# robin
FILE='/home/joshua/gopro/20210605-copperopolis/GX010037.MP4'
SEEKTIME=0

# descent
#FILE='/home/joshua/gopro/20210605-copperopolis/GX010031.MP4'
#SEEKTIME=0

FITFILE='/home/joshua/gopro/20210605-copperopolis/Copperopolis_Road_Race_off_the_back_7_19_but_at_least_I_didn_t_DNF_.fit'
TIMEFUDGE=36.58

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

cadence = f.interpolator('cadence', flatten_zeroes = datetime.timedelta(seconds = 2.0))
heart_rate = f.interpolator('heart_rate')
speed_kph = f.interpolator('speed')
dist_km = f.interpolator('distance')
temp_c = f.interpolator('temperature')
latitude = f.interpolator('position_lat')
longitude = f.interpolator('position_long')
altitude = f.interpolator('altitude')
grade = f.interpolator('grade')

def paint(ctx, w, h, tm):
    cadence_gauge.render(ctx, cadence.value(tm))
    heart_rate_gauge.render(ctx, heart_rate.value(tm))
    speed_gauge.render(ctx, speed_kph.value(tm, transform = lambda v: v * 0.62137119))
    temp_gauge.render(ctx, temp_c.value(tm, transform = lambda v: (v * 9 / 5) + 32))
    dist_gauge.render(ctx, dist_km.value(tm, transform = lambda v: v * 0.62137119))
    map.render(ctx, latitude.value(tm), longitude.value(tm))
    elevmap.render(ctx, dist_km.value(tm), altitude.value(tm), grade.value(tm))

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
    
    def __init__(self, painter, start_time):
        super(GstOverlayGPS, self).__init__()
        self.painter = painter
        self.video_start_time = start_time
        self.last_tm = time.time()
    
    def do_transform_ip(self, buffer):
        tst = time.time()
        caps = self.srcpad.get_current_caps()
        h = caps.get_structure(0).get_value("height")
        w = caps.get_structure(0).get_value("width")
        
        with map_gst_buffer(buffer, Gst.MapFlags.READ) as data:
            surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h)
            ctx = cairo.Context(surf)
            self.painter(ctx, w, h, self.video_start_time + datetime.timedelta(seconds = self.segment.position / 1000000000))
        
        print(f"transform took {(time.time() - tst) * 1000:.1f}ms, {1 / (time.time() - self.last_tm):.1f} fps")
        self.last_tm = time.time()
        
        return Gst.FlowReturn.OK

class VideoSourceGoPro:
    def __init__(self, filename, flip = True, h265 = True, framerate = 30000/1001, timefudge = datetime.timedelta(seconds = 0)):
        self.filename = filename
        self.flip = flip
        self.h265 = h265
        self.framerate = framerate # needed until we can pull this out of the file with libav
        self.timefudge = timefudge
    
    def add_to_pipeline(self, pipeline):
        """Returns a tuple of GstElements that have src pads for *decoded* video and *encoded* audio."""
        def mkelt(eltype):
            elt = Gst.ElementFactory.make(eltype, None)
            assert elt
            pipeline.add(elt)
            return elt

        filesrc = mkelt("filesrc")
        filesrc.set_property("location", self.filename)
        
        multiqueue_vpad = None
        multiqueue_apad = None

        qtdemux = mkelt("qtdemux")
        filesrc.link(qtdemux)
        def qtdemux_pad_callback(qtdemux, pad):
            name = pad.get_name()
            if name == "video_0":
                pad.link(multiqueue_vpad)
            elif name == "audio_0":
                pad.link(multiqueue_apad)
            else:
                print(f"qtdemux unknown output pad {name}?")
        qtdemux.connect("pad-added", qtdemux_pad_callback) # will not fire until preroll

        multiqueue = mkelt("multiqueue")
        multiqueue_vpad = multiqueue.get_request_pad("sink_%u")
        multiqueue_apad = multiqueue.get_request_pad("sink_%u")
        # pads linked above

        # audio pipeline
        queuea0 = mkelt("queue")
        multiqueue.get_static_pad(f"src_{multiqueue_apad.get_name().split('_')[1]}").link(queuea0.get_static_pad("sink"))
        aout = queuea0
        
        # video pipeline
        avdec = mkelt("avdec_h265" if self.h265 else "avdec_h264")
        multiqueue.get_static_pad(f"src_{multiqueue_vpad.get_name().split('_')[1]}").link(avdec.get_static_pad("sink"))

        queuev1 = mkelt("queue")
        avdec.link(queuev1)

        videoconvert_in = mkelt("videoconvert")
        queuev1.link(videoconvert_in)
        vout = videoconvert_in

        if self.flip:
            videoflip = mkelt("videoflip")
            videoflip.set_property("method", "rotate-180")
            videoconvert_in.link(videoflip)
            vout = videoflip
        
        return (aout, vout)
    
    def decode_audio(self, pipeline, aout):
        def mkelt(eltype):
            elt = Gst.ElementFactory.make(eltype, None)
            assert elt
            pipeline.add(elt)
            return elt

        avdec_aac = mkelt("avdec_aac")
        aout.link(avdec_aac)

        audioconvert = mkelt("audioconvert")
        avdec_aac.link(audioconvert)

        audioresample = mkelt("audioresample")
        audioconvert.link(audioresample)
        
        return audioresample
    
    def start_time(self):
        # Load the timecode.  XXX: do this with libav python
        (fd, tmcd_out) = tempfile.mkstemp()
        os.system(f"ffmpeg -v 0 -i {self.filename} -map 0:d:0 -y -f data {tmcd_out}")
        with open(tmcd_out, "rb") as f:
            tmcd_frames = struct.unpack(">I", f.read())[0]
        tmcd_secs = tmcd_frames / self.framerate
        os.unlink(tmcd_out)
        # XXX: pull this DMY out somehow (ctime from libav python?)
        return datetime.datetime(year = 2021, month = 6, day = 5) + datetime.timedelta(seconds = tmcd_secs) + self.timefudge # this is LOCAL TIME, timefudge must fix it to UTC

class RenderLoop:
    def __init__(self, input, painter):
        self.input = input
        self.painter = painter
        self.start_time = input.start_time()
    
    def preview(self, seek = 0.0):
        """Set up a Gstreamer preview pipeline, and begin playing it."""

        pipeline = Gst.Pipeline.new("pipeline")
        
        (aout, vout) = self.input.add_to_pipeline(pipeline)
        adec = self.input.decode_audio(pipeline, aout)

        def mkelt(eltype):
            elt = Gst.ElementFactory.make(eltype, None)
            assert elt
            pipeline.add(elt)
            return elt

        autoaudiosink = mkelt("autoaudiosink")
        adec.link(autoaudiosink)

        gpsoverlay = GstOverlayGPS(paint, self.start_time)
        pipeline.add(gpsoverlay)
        vout.link(gpsoverlay)

        videoconvert_out = mkelt("videoconvert")
        gpsoverlay.link(videoconvert_out)

        queuev2 = mkelt("queue")
        videoconvert_out.link(queuev2)

        autovideosink = mkelt("autovideosink")
        queuev2.link(autovideosink)

        loop = GLib.MainLoop()
        did_seek = False

        def on_message(bus, message):
            mtype = message.type
            if mtype == Gst.MessageType.STATE_CHANGED:
                old_state, new_state, pending_state = message.parse_state_changed()
                if new_state == Gst.State.PLAYING:
                    q = Gst.Query.new_seeking(Gst.Format.TIME)
                    pipeline.query(q)
                    fmt, seek_enabled, start, end = q.parse_seeking()
            
                    nonlocal did_seek, seek
                    if not did_seek and seek > 0:
                        pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, seek * Gst.SECOND) 
                        did_seek = True
            elif mtype == Gst.MessageType.EOS:
                print("EOS")
                loop.quit()
            elif mtype == Gst.MessageType.ERROR:
                print("Error!")
            elif mtype == Gst.MessageType.WARNING:
                print("Warning!")
            return True

        bus = pipeline.get_bus()
        bus.connect("message", on_message)
        bus.add_signal_watch()

        pipeline.set_state(Gst.State.PLAYING)

        try:
            loop.run()
        finally:
            loop.quit()
    
    def encode(self, output):
        """Set up a Gstreamer encode, and run it."""

        pipeline = Gst.Pipeline.new("pipeline")
        
        (aout, vout) = self.input.add_to_pipeline(pipeline)

        def mkelt(eltype):
            elt = Gst.ElementFactory.make(eltype, None)
            assert elt
            pipeline.add(elt)
            return elt

        gpsoverlay = GstOverlayGPS(paint, self.start_time)
        pipeline.add(gpsoverlay)
        vout.link(gpsoverlay)

        videoconvert_out = mkelt("videoconvert")
        gpsoverlay.link(videoconvert_out)
        
        x264enc = mkelt("x264enc")
        x264enc.set_property("pass", 5) # constant quality
        x264enc.set_property("speed-preset", 2) # superfast
        x264enc.set_property("quantizer", 18) # ???
        videoconvert_out.link(x264enc)
        
        x264q = mkelt("queue")
        x264enc.link(x264q)
        
        mp4mux = mkelt("mp4mux")
        x264q.link(mp4mux)
        aout.link(mp4mux)
        
        filesink = mkelt("filesink")
        filesink.set_property("location", output)
        mp4mux.link(filesink)
        
        pipeline.use_clock(None)

        loop = GLib.MainLoop()
        def on_message(bus, message):
            mtype = message.type
            if mtype == Gst.MessageType.STATE_CHANGED:
                pass
            elif mtype == Gst.MessageType.EOS:
                print("EOS")
                pipeline.set_state(Gst.State.NULL)
                loop.quit()
            elif mtype == Gst.MessageType.ERROR:
                print("Error!")
            elif mtype == Gst.MessageType.WARNING:
                print("Warning!")
            return True

        bus = pipeline.get_bus()
        bus.connect("message", on_message)
        bus.add_signal_watch()

        pipeline.set_state(Gst.State.PLAYING)

        try:
            loop.run()
        finally:
            pipeline.send_event(Gst.Event.new_eos())
            pipeline.set_state(Gst.State.NULL)
            loop.quit()

RenderLoop(VideoSourceGoPro(FILE, timefudge = datetime.timedelta(hours = 7, seconds = -TIMEFUDGE)), painter = paint).encode("robin.mp4")
