"""
Global rendering parameters that many widgets may wish to use.
"""

from gpsrenda.utils import merge_dict

globals = {
    'style': {
        'text_shadows': False,
        'bar_gradients': False,
        'bar_gradients_tint': 0.0,
        'background_gradients': False,
        'fonts': {
          'proportional': 'Ubuntu',
          'monospace': 'Ubuntu Mono',
        },
        'padding_strings': {
          'dummy_value': None,
          'dummy_caption': 'mph',
        },
    },
    'units': 'metric',
    'video': {
        'force_rotation': None,
        'engine': None,
        'scale': None,
        'gstreamer': {
            'h265': False,
            'pcm_audio': False,
            'framerate': 30000/1001,
            'speed_preset': 'veryfast',
            'bitrate': 60000,
            'encode_threads': 4,
            'decoder': None,
            'encoder': 'x264', # x264 is actually just as fast on my machine as the hardware encoder ... and the video quality is a lot better for ~ the same bitrate
            'x264_profile': 'high', # yuv420, for youtube and davinci resolve compatibility... can also be high-4:2:2, high-4:4:4, baseline, ...
        }
    },
}

def set_globals(params):
    merge_dict(globals, params)
