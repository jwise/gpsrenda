import logging

import moviepy.editor as mpy
import cairo
import numpy as np

from gpsrenda.globals import globals
from gpsrenda.utils import extract_start_time, timestamp_to_seconds, is_flipped

from .engines import register_engine

logger = logging.getLogger(__name__)

class RenderEngineMoviepy:
    def __init__(self, renderfn, adjust_time_offset = None):
        self.renderfn = renderfn

    def _mkclip(self, src):
        clip = mpy.VideoFileClip(src)
        if globals['video']['force_rotation'] is not None:
            want_flipped = globals['video']['force_rotation'] == 180
            if is_flipped(src) != want_flipped:
                clip = clip.rotate(180)
        start_t = timestamp_to_seconds(extract_start_time(src))

        def make_frame(t):
            frame = clip.get_frame(t)
            h, w = frame.shape[:2]
            alpha = np.zeros((h, w, 1), dtype=frame.dtype)
            argb_frame = np.concatenate([frame[:,:,::-1], alpha], axis=-1)

            surf = cairo.ImageSurface.create_for_data(argb_frame, cairo.FORMAT_ARGB32, w, h)
            ctx = cairo.Context(surf)

            self.renderfn(ctx, t + start_t)

            buf = surf.get_data()
            out_frame = np.ndarray(shape=argb_frame.shape, dtype=argb_frame.dtype, buffer=buf)
            return out_frame[:,:,:3][:,:,::-1]

        composite_clip = mpy.VideoClip(make_frame, duration=clip.duration)
        composite_clip.audio = clip.audio

        return (clip, composite_clip)

    def render(self, src, dest):
        clip, outclip = self._mkclip(src)

        outclip.audio = clip.audio
        outclip.write_videofile(
            dest,
            fps=clip.fps,
            audio_codec='aac',
            threads=None,
            ffmpeg_params=[
                '-crf', '30',
            ]
        )

    def preview(self, src, seek = 0.0):
        clip, outclip = self._mkclip(src)
        outclip.resize((960, 640)).preview(fps=15, audio=False)

register_engine(RenderEngineMoviepy, name='moviepy')
