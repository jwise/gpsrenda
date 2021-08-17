import sys
import logging
import time
import datetime

import cairo
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('GstBase', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GstApp, GstBase, GstVideo, GLib, GObject

from gpsrenda.globals import globals
from gpsrenda.utils import extract_start_time, timestamp_to_seconds, is_flipped

from .engines import register_engine

from .gst_hacks import map_gst_buffer

Gst.init(sys.argv)

logger = logging.getLogger(__file__)

class VideoSourceGoPro:
    def __init__(self, filename):
        self.filename = filename
        if globals['video']['force_rotation'] is None:
            self.flip = is_flipped(src)
        else:
            self.flip = globals['video']['force_rotation'] == 180
        self.h265 = globals['video']['gstreamer']['h265'] # needed until we can pull this out of the file with libav
        self.framerate = globals['video']['gstreamer']['framerate'] # needed until we can pull this out of the file with libav

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
        avdec.set_property("max-threads", 4)

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
        return timestamp_to_seconds(extract_start_time(self.filename))

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
            self.painter(ctx, self.video_start_time + self.segment.position / 1000000000)

        self.frames_processed += 1
        if TRANSFORM_VERBOSE:
            print(f"transform took {(time.time() - tst) * 1000:.1f}ms, {1 / (time.time() - self.last_tm):.1f} fps")
        self.last_tm = time.time()

        return Gst.FlowReturn.OK

class RenderEngineGstreamer:
    def __init__(self, renderfn, adjust_time_offset = None):
        self.renderfn = renderfn
        self.adjust_time_offset = adjust_time_offset

    def render(self, src, dest):
        """Set up a Gstreamer encode, and run it."""

        input = VideoSourceGoPro(src)

        pipeline = Gst.Pipeline.new("pipeline")

        (aout, vout) = input.add_to_pipeline(pipeline)

        def mkelt(eltype):
            elt = Gst.ElementFactory.make(eltype, None)
            assert elt
            pipeline.add(elt)
            return elt

        gpsoverlay = GstOverlayGPS(self.renderfn, input.start_time())
        pipeline.add(gpsoverlay)
        vout.link(gpsoverlay)

        videoconvert_out = mkelt("videoconvert")
        gpsoverlay.link(videoconvert_out)

        x264enc = mkelt("x264enc")
        x264enc.set_property("pass", "qual") # constant quality
        x264enc.set_property("speed-preset", globals['video']['gstreamer']['speed_preset'])
        x264enc.set_property("bitrate", globals['video']['gstreamer']['bitrate']) # should be quantizer for CRF mode in pass=qual, but it isn't?  oh, well
        x264enc.set_property("threads", globals['video']['gstreamer']['encode_threads'])
        videoconvert_out.link(x264enc)

        x264q = mkelt("queue")
        x264enc.link(x264q)

        mp4mux = mkelt("mp4mux")
        x264q.link(mp4mux)
        aout.link(mp4mux)

        filesink = mkelt("filesink")
        filesink.set_property("location", dest)
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
        alldone = False
        def on_timer():
            if alldone:
                return False
            (_, pos) = pipeline.query_position(Gst.Format.TIME)
            (_, dur) = pipeline.query_duration(Gst.Format.TIME)
            now = time.time() - starttime
            if dur <= 1000 or now <= 1:
                print("starting up...", end='\r')
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
        alldone = True
        print("")

    def preview(self, src, seek = 0.0):
        """Set up a Gstreamer preview pipeline, and begin playing it."""

        input = VideoSourceGoPro(src)

        pipeline = Gst.Pipeline.new("pipeline")

        (aout, vout) = input.add_to_pipeline(pipeline)
        adec = input.decode_audio(pipeline, aout)

        def mkelt(eltype):
            elt = Gst.ElementFactory.make(eltype, None)
            assert elt
            pipeline.add(elt)
            return elt

        autoaudiosink = mkelt("autoaudiosink")
        adec.link(autoaudiosink)

        gpsoverlay = GstOverlayGPS(self.renderfn, input.start_time())
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

        def do_seek(ofs):
            (_, now) = pipeline.query_position(Gst.Format.TIME)
            now += ofs * Gst.SECOND
            pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, now)
            print(f"\nseeked to t={now / Gst.SECOND}")

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
            elif mtype == Gst.MessageType.ELEMENT:
                (isnav, event) = GstVideo.Navigation.message_parse_event(message)
                if isnav:
                    evtype = GstVideo.Navigation.event_get_type(event)
                    # GST_NAVIGATION_EVENT_MOUSE_MOVE, GST_NAVIGATION_EVENT_KEY_RELEASE, MOUSE_BUTTON_PRESS, ...
                    if evtype == GstVideo.NavigationEventType.KEY_PRESS:
                        (iskey, key) = GstVideo.Navigation.event_parse_key_event(event)
                        if key == 'Left':
                            do_seek(-5)
                        elif key == 'Right':
                            do_seek(5)
                        elif key == 'minus':
                            self.adjust_time_offset(-0.2)
                        elif key == 'equal':
                            self.adjust_time_offset(0.2)
                        elif key == 'bracketleft':
                            self.adjust_time_offset(-2)
                        elif key == 'bracketright':
                            self.adjust_time_offset(2)
                        elif key == 'q':
                            loop.quit()
                        else:
                            print(f"unknown keypress: {key}")
            return True

        alldone = False
        def on_timer():
            if alldone:
                return False
            (_, pos) = pipeline.query_position(Gst.Format.TIME)
            (_, dur) = pipeline.query_duration(Gst.Format.TIME)
            if dur <= 1000:
                print("starting up...", end='\r')
                return True
            print(f"{pos / Gst.SECOND:.1f} / {dur / Gst.SECOND:.1f}", end='\r')
            return True
        GLib.timeout_add(100, on_timer)

        bus = pipeline.get_bus()
        bus.connect("message", on_message)
        bus.add_signal_watch()

        pipeline.set_state(Gst.State.PLAYING)

        try:
            loop.run()
        finally:
            loop.quit()
            alldone = True
        print("")

register_engine(RenderEngineGstreamer, name='gstreamer')
