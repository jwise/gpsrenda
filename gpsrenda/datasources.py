import fitparse
import numpy as np
from scipy.interpolate import interp1d

from datetime import datetime

from gpsrenda.utils import timestamp_to_seconds


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

        self.interpolators = {}
        for name, values in self.fields.items():
            val_array = np.array(values)
            x, y = val_array[:,0], val_array[:,1]
            self.interpolators[name] = interp1d(x, y, kind='linear', assume_sorted=True)

        self.grade_seconds = grade_seconds

    def altitude(t):
        return self.interpolators['altitude'](t)

    def cadence(t):
        return self.interpolators['cadence'](t)

    def distance(t):
        return self.interpolators['distnace'](t)

    def grade(t):
        try:
            result = self.interpolators['grade'](t)
        except KeyError:
            dt = self.grade_seconds
            # 100 % / 1000 m per km  --> 1/10
            result = (self.altitude(t + dt) - self.altitude(t - dt)) / (self.distance(t + dt) - self.distance(t - dt)) / 10
        return result

    def heart_rate(t):
        return self.interpolators['power'](t)

    def lat(t):
        return self.interpolators['position_lat'](t)

    def lon(t):
        return self.interpolators['position_long'](t)

    def power(t):
        return self.interpolators['power'](t)

    def speed(t):
        return self.interpolators['speed'](t)

    def temperature(t):
        return self.interpolators['temperature'](t)
