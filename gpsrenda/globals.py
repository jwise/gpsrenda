"""
Global rendering parameters that many widgets may wish to use.
"""

from gpsrenda.utils import merge_dict

globals = {
    'style': {
        'text_shadows': False,
        'bar_gradients': False,
        'background_gradients': False,
    },
}

def set_globals(params):
    merge_dict(globals, params)
