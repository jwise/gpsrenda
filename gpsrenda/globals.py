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
}

def set_globals(params):
    merge_dict(globals, params)
