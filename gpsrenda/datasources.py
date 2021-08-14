import fitparse
import numpy as np
import math
from functools import partial

from datetime import datetime, timedelta
import logging

from gpsrenda.utils import timestamp_to_seconds, seconds_to_timestamp, merge_dict


logger = logging.getLogger(__file__)


DEFAULT_DATA_CONFIG = {
    'altitude': {
        'lag': 0
    },
    'grade': {
        'averaging_time': 2
    },
    'gap_flatten_time': 2,
}

def interp1d_zeroing(x, y, t, flatten_time = math.inf):
    # easy edge cases first
    if t < x[0]:
        return NaN
    if t > x[-1]:
        return NaN

    argt = np.searchsorted(x, t) # x[argt] >= t
    if argt == 0:
        return y[0]

    # do we need to flatten?
    pre = (x[argt-1], y[argt-1])
    post = (x[argt], y[argt])

    if (t - pre[0]) > flatten_time:
        pre = (x[argt] - flatten_time, 0.0)

    if (post[0] - t) > flatten_time:
        post = (x[argt-1] + flatten_time, 0.0)

    if post[0] < pre[0]: # we are flattening both
        return 0.0

    # do the lerp
    alpha = (t - pre[0]) / (post[0] - pre[0])
    return pre[1] * (1.0 - alpha) + post[1] * alpha

class FitDataSource:
    def __init__(self, file_path, config):
        self.config = merge_dict(DEFAULT_DATA_CONFIG, config)

        fit_file = fitparse.FitFile(file_path)
        messages = list(fit_file.get_messages('record'))

        self.fields = {}
        for message in messages:
            data = message.get_values()
            time = timestamp_to_seconds(data.pop('timestamp'))
            for key, value in data.items():
                try:
                    self.fields[key].append((time, value))
                except KeyError:
                    self.fields[key] = [(time, value)]

        self._interpolators = {}
        self._interpolators_zeroing = {}
        for name, values in self.fields.items():
            val_array = np.array(values, dtype=np.float)
            # It is possible for the fit file to contain a few or all NaNs due to missing / corrupted data
            # Drop nans before interpolation
            nans = np.isnan(val_array[:,1])
            if np.all(nans):
                logger.warn(f"{name} data contained only NaNs")
            else:
                nan_idx, = np.where(nans)
                if len(nan_idx) > 0:
                    times_str = ", ".join([str(timedelta(seconds=val_array[idx,0] - val_array[0,0])) for idx in nan_idx[:10]])
                    if len(nan_idx) > 10:
                        times_str += ", ..."
                    logger.warn(f"Found {len(nan_idx):d} NaN(s) in {name} data at {times_str:s}")
                not_nan_idx, = np.where(np.logical_not(nans))
                x, y = val_array[not_nan_idx,0], val_array[not_nan_idx,1]
                self._interpolators[name] = partial(interp1d_zeroing, x, y)

    def altitude(self, t):
        return self._interpolators['altitude'](t + self.config['altitude']['lag'])

    def cadence(self, t):
        return self._interpolators['cadence'](t, flatten_time = self.config['gap_flatten_time'])

    def distance(self, t):
        return self._interpolators['distance'](t)

    def grade(self, t):
        try:
            result = self._interpolators['grade'](t, flatten_time = self.config['gap_flatten_time'])
        except KeyError:
            dt = self.config['grade']['averaging_time'] / 2
            den = self.distance(t + dt) - self.distance(t - dt)
            if den == 0:
                result = 0.0
            else:
                result = (self.altitude(t + dt) - self.altitude(t - dt)) / den * 100
        return result

    def heart_rate(self, t):
        return self._interpolators['heart_rate'](t)

    def lat(self, t):
        return self._interpolators['position_lat'](t)

    def lon(self, t):
        return self._interpolators['position_long'](t)

    def power(self, t):
        return self._interpolators['power'](t, flatten_time = self.config['gap_flatten_time'])

    def speed(self, t):
        return self._interpolators['speed'](t, flatten_time = self.config['gap_flatten_time'])

    def temperature(self, t):
        return self._interpolators['temperature'](t)
