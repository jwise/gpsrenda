import fitparse
import numpy as np
from scipy.interpolate import interp1d

from datetime import datetime, timedelta
import logging

from gpsrenda.utils import timestamp_to_seconds, seconds_to_timestamp


logger = logging.getLogger(__file__)


class FitDataSource:
    def __init__(self, file_path, grade_seconds=1):
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
                self._interpolators[name] = interp1d(x, y, kind='linear', bounds_error=False, assume_sorted=True)

        self.grade_seconds = grade_seconds

    def altitude(self, t):
        return self._interpolators['altitude'](t)

    def cadence(self, t):
        return self._interpolators['cadence'](t)

    def distance(self, t):
        return self._interpolators['distance'](t)

    def grade(self, t):
        try:
            result = self._interpolators['grade'](t)
        except KeyError:
            dt = self.grade_seconds
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
        return self._interpolators['power'](t)

    def speed(self, t):
        return self._interpolators['speed'](t)

    def temperature(self, t):
        return self._interpolators['temperature'](t)
