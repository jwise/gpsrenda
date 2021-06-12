import sys
import os
import time
import datetime

import cairo
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('GstBase', '1.0')
from gi.repository import Gst, GstApp, GstBase, GLib, GObject

from .gst_hacks import map_gst_buffer

Gst.init(sys.argv)

TRANSFORM_VERBOSE = False

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
        self.frames_processed = 0
    
    def do_transform_ip(self, buffer):
        tst = time.time()
        caps = self.srcpad.get_current_caps()
        h = caps.get_structure(0).get_value("height")
        w = caps.get_structure(0).get_value("width")
        
        with map_gst_buffer(buffer, Gst.MapFlags.READ) as data:
            surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h)
            ctx = cairo.Context(surf)
            self.painter(ctx, w, h, self.video_start_time + datetime.timedelta(seconds = self.segment.position / 1000000000))
        
        self.frames_processed += 1
        if TRANSFORM_VERBOSE:
            print(f"transform took {(time.time() - tst) * 1000:.1f}ms, {1 / (time.time() - self.last_tm):.1f} fps")
        self.last_tm = time.time()
        
        return Gst.FlowReturn.OK

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

        gpsoverlay = GstOverlayGPS(self.painter, self.start_time)
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

        gpsoverlay = GstOverlayGPS(self.painter, self.start_time)
        pipeline.add(gpsoverlay)
        vout.link(gpsoverlay)

        videoconvert_out = mkelt("videoconvert")
        gpsoverlay.link(videoconvert_out)
        
        x264enc = mkelt("x264enc")
        x264enc.set_property("pass", "qual") # constant quality
        x264enc.set_property("speed-preset", "veryfast")
        x264enc.set_property("bitrate", 60000) # should be quantizer for CRF mode in pass=qual, but it isn't?  oh, well
        x264enc.set_property("threads", 4)
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
                print("\nEOS")
                pipeline.set_state(Gst.State.NULL)
                loop.quit()
            elif mtype == Gst.MessageType.ERROR:
                print("\nError!")
            elif mtype == Gst.MessageType.WARNING:
                print("\nWarning!")
            return True

        bus = pipeline.get_bus()
        bus.connect("message", on_message)
        bus.add_signal_watch()
        
        starttime = time.time()
        def on_timer():
            (_, pos) = pipeline.query_position(Gst.Format.TIME)
            (_, dur) = pipeline.query_duration(Gst.Format.TIME)
            now = time.time() - starttime
            if dur == 0 or now == 0:
                print("starting up...")
                return True
            now = datetime.timedelta(seconds = now)
            pos = datetime.timedelta(microseconds = pos / 1000)
            dur = datetime.timedelta(microseconds = dur / 1000)
            print(f"{pos / dur * 100:.1f}% ({pos/now:.2f}x realtime; {pos} / {dur}; {gpsoverlay.frames_processed} frames)", end='\r')
            return True
        GLib.timeout_add(200, on_timer)

        pipeline.set_state(Gst.State.PLAYING)

        try:
            loop.run()
        finally:
            pipeline.send_event(Gst.Event.new_eos())
            pipeline.set_state(Gst.State.NULL)
            loop.quit()
        print("")
