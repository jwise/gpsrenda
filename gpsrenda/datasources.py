import fitparse
import numpy as np
import math
import pickle
from functools import partial

from datetime import datetime, timedelta
import logging

from gpsrenda.utils import timestamp_to_seconds, seconds_to_timestamp, merge_dict

logger = logging.getLogger(__name__)

DEFAULT_DATA_CONFIG = {
    'altitude': {
        'lag': 0
    },
    'position': {
        'lag': 0
    },
    'grade': {
        'averaging_time': 2,
        'min_distance': 8 # 2.6mph at 7s averaging time
    },
    'gap_flatten_time': 2,
}

def interp1d_zeroing(x, y, t, flatten_time = math.inf):
    # easy edge cases first
    if t < x[0]:
        return math.nan
    if t > x[-1]:
        return math.nan

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

class ParsedFitData:
    """
    Loading large FIT files can be very slow, so we create a pickleable
    ParsedFitData structure that can be used to create a cache later.
    """

    # Bump this every time you change anything in ParsedFitData.
    VERSION = 1

    def __init__(self, file_path):
        self.version = ParsedFitData.VERSION

        fit_file = fitparse.FitFile(file_path)

        self.file_id = list(fit_file.get_messages('file_id'))[0].get_values()

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

    def save_cache(self, cache_path):
        with open(cache_path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load_cache(cls, cache_path):
        with open(cache_path, "rb") as f:
            self = pickle.load(f)
            if self.version != ParsedFitData.VERSION:
                raise ValueError("incorrect cache version f{self.version} (want f{ParsedFitData.VERSION}) in file f{cache_path}")
            return self

class FitDataSource:
    GARMIN530_QUIRKS = {
        'altitude': { 'lag': 25 },
        'grade': { 'averaging_time': 4 },
    }

    GARMIN520_QUIRKS = {
        'altitude': { 'lag': 5 },
        'grade': { 'averaging_time': 7 },
    }
    
    LEZYNE_QUIRKS = {
        'grade': { 'averaging_time': 7 },
    }
    
    WAHOO_QUIRKS = {
        'position': { 'lag': 1 },
    }

    DEVICES = [
        ( { 'manufacturer': 'garmin', 'garmin_product': 3121 }, { 'name': 'Garmin Edge 530', 'quirks': GARMIN530_QUIRKS } ),
        ( { 'manufacturer': 'garmin', 'garmin_product': 'edge520' }, { 'name': 'Garmin Edge 520', 'quirks': GARMIN520_QUIRKS } ),
        ( { 'manufacturer': 'wahoo_fitness', 'product': 31 }, { 'name': 'Wahoo ELEMNT BOLT', 'quirks': WAHOO_QUIRKS } ),
        ( { 'manufacturer': 'hammerhead', 'product_name': 'Karoo 2' }, { 'name': 'Hammerhead Karoo 2', 'quirks': {} } ),
        ( { 'manufacturer': 'lezyne', 'product': 11 }, { 'name': 'Lezyne Mega XL', 'quirks': LEZYNE_QUIRKS }),
    ]

    def __init__(self, file_path, config):
        cache_name = f"{file_path}.gpsrendacache"
        try:
            logger.debug(f"trying to load FIT cache from {cache_name}")
            parsed = ParsedFitData.load_cache(cache_name)
        except:
            logger.info(f"could not load from FIT cache {cache_name}; loading FIT file the hard way (this may take a moment)")
            parsed = ParsedFitData(file_path)
            parsed.save_cache(cache_name)

        self.fields = parsed.fields

        # Apply quirks as early as possible.
        self.config = DEFAULT_DATA_CONFIG
        found_device = False
        for params, val in FitDataSource.DEVICES:
            if not all([ parsed.file_id.get(k, None) == params[k] for k in params ]):
                continue
            logger.debug(f"FIT file comes from supported device {val['name']}")
            self.config = merge_dict(self.config, val['quirks'])
            found_device = True
            break

        if not found_device:
            logger.warn(f"FIT file comes from unsupported device with file_id {parsed.file_id} -- add it to datasources.py to silence this warning (and submit a pull request!)")

        # Allow user to override quirks.
        self.config = merge_dict(self.config, config)

        self._interpolators = {}
        for name, values in parsed.fields.items():
            # fitparse gets this wrong, and maps 0% right to 'right'.
            if "left_right_balance" in name:
                values = [ (t, 0x80 if v == 'right' else v) for t,v in values ]

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
        return self._interpolators['distance'](t + self.config['position']['lag'])

    def grade(self, t):
        try:
            result = self._interpolators['grade'](t, flatten_time = self.config['gap_flatten_time'])
        except KeyError:
            dt = self.config['grade']['averaging_time'] / 2
            den = self.distance(t + dt) - self.distance(t - dt)
            if den < self.config['grade']['min_distance']:
                result = 0.0
            else:
                result = (self.altitude(t + dt + self.config['altitude']['lag']) - self.altitude(t - dt + self.config['altitude']['lag'])) / den * 100
        return result

    def heart_rate(self, t):
        return self._interpolators['heart_rate'](t)

    def lat(self, t):
        return self._interpolators['position_lat'](t + self.config['position']['lag'])

    def lon(self, t):
        return self._interpolators['position_long'](t + self.config['position']['lag'])

    def power(self, t):
        return self._interpolators['power'](t, flatten_time = self.config['gap_flatten_time'])

    def speed(self, t):
        return self._interpolators['speed'](t + self.config['position']['lag'], flatten_time = self.config['gap_flatten_time'])

    def temperature(self, t):
        return self._interpolators['temperature'](t)
