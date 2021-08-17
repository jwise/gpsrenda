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
    },
    'units': 'metric',
    'video': {
        'force_rotation': None,
        'engine': None,
        'gstreamer': {
            'h265': True,
            'framerate': 30000/1001,
            'speed_preset': 'veryfast',
            'bitrate': 60000,
            'encode_threads': 4,
        }
    },
}

def set_globals(params):
    merge_dict(globals, params)
