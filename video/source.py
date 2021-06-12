import datetime
import tempfile
import os
import struct

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('GstBase', '1.0')
from gi.repository import Gst, GstApp, GstBase, GLib, GObject

class VideoSourceGoPro:
    def __init__(self, filename, flip = True, h265 = True, framerate = 30000/1001, date = None, timefudge = datetime.timedelta(seconds = 0)):
        self.filename = filename
        self.flip = flip
        self.h265 = h265
        self.framerate = framerate # needed until we can pull this out of the file with libav
        self.date = date # needed until we can pull this out of the file with libav
        if self.date is None:
            raise ValueError("recording date is required")
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
        # Load the timecode.  XXX: do this with libav python
        (fd, tmcd_out) = tempfile.mkstemp()
        os.system(f"ffmpeg -v 0 -i {self.filename} -map 0:d:0 -y -f data {tmcd_out}")
        with open(tmcd_out, "rb") as f:
            tmcd_frames = struct.unpack(">I", f.read())[0]
        tmcd_secs = tmcd_frames / self.framerate
        os.unlink(tmcd_out)
        # XXX: pull this DMY out somehow (ctime from libav python?)
        return self.date + datetime.timedelta(seconds = tmcd_secs) + self.timefudge # this is LOCAL TIME, timefudge must fix it to UTC
