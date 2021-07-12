from gpsrenda.widgets import *
from gpsrenda.utils import timestamp_to_seconds, km_to_mi, c_to_f

STYLE_TABLE = {
    'hbar': GaugeHorizontal,
    'vbar': GaugeVertical,
    'map': GaugeMap,
    'grade': GaugeElevationMap,
}

class SpeedWidget:
    def __init__(self, data_source, x, y, style='hbar', units='metric'):
        self.data_source = data_source
        self.units = units
        gauge_class = STYLE_TABLE[style]
        caption = 'mph' if units == 'imperial' else 'kph'

        colors = [(0, [0.2, 0.0, 0.6]),
                  (25, [0.0, 0.6, 0.0]),
                  (50, [0.8, 0.0, 0.0])]

        if units == 'imperial':
            for idx, (val, rgb) in enumerate(colors):
                colors[idx] = (km_to_mi(val), rgb)

        gauge = gauge_class(x, y, label="{val:.1f}", dummy_label="99.9", caption=caption,
                            data_range=colors)
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.speed(t) * 60 * 60 / 1000
        if self.units == 'imperial':
            value = km_to_mi(value)
        self.gauge.render(context, value)


class CadenceWidget:
    def __init__(self, data_source, x, y, style='hbar'):
        self.data_source = data_source
        gauge_class = STYLE_TABLE[style]
        gauge = gauge_class(x, y, label="{val:.0f}", dummy_label="999", caption="rpm",
                            data_range=[(60, [0.8, 0.0, 0.0]),
                                        (90, [0.0, 0.6, 0.0]),
                                        (120, [0.8, 0.0, 0.0])])
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.interpolators['cadence'](t)
        self.gauge.render(context, value)


class HeartRateWidget:
    def __init__(self, data_source, x, y, style='hbar'):
        self.data_source = data_source
        gauge_class = STYLE_TABLE[style]
        gauge = gauge_class(x, y, label="{val:.0f}", dummy_label="999", caption="bpm",
                            data_range=[(100, [0.2, 0.0, 0.6]),
                                        (200, [0.8, 0.0, 0.0])])
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.interpolators['heart_rate'](t)
        self.gauge.render(context, value)


class PowerWidget:
    def __init__(self, data_source, x, y, style='hbar'):
        self.data_source = data_source
        gauge_class = STYLE_TABLE[style]
        gauge = gauge_class(x, y, label="{val:.0f}", dummy_label="999", caption="W",
                            data_range=[(0, (0, 0.6, 0)),
                                        (300, (0.2, 0.6, 0.0)),
                                        (800, (0.8, 0.0, 0.0))])
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.interpolators['power'](t)
        self.gauge.render(context, value)


class TemperatureWidget:
    def __init__(self, data_source, x, y, style='vbar', units='metric'):
        self.data_source = data_source
        self.units = units
        gauge_class = STYLE_TABLE[style]
        suffix = '°F' if units == 'imperial' else '°C'

        colors = [(5, (0.6, 0, 0)),
                  (20, (0.0, 0.6, 0.0)),
                  (35, (0.0, 0.0, 1.0))]

        if units == 'imperial':
            for idx, (val, rgb) in enumerate(colors):
                colors[idx] = (c_to_f(val), rgb)

        gauge = gauge_class(x, y, label="{val:.0f}"+suffix, dummy_label="0.0",
                            data_range=colors)
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.interpolators['temperature'](t)
        if self.units == 'imperial':
            value = c_to_f(value)
        self.gauge.render(context, value)


class DistanceWidget:
    def __init__(self, data_source, x, y, w, style='hbar', units='metric'):
        self.data_source = data_source
        self.units = units
        gauge_class = STYLE_TABLE[style]
        suffix = 'mi' if units == 'imperial' else 'km'

        total_distance = data_source.fields['distance'][-1][1]

        if units == 'imperial':
            total_distance = km_to_mi(total_distance) / 1000

            colors = [(0, [0.75, 0.75, 0.75]),
                      (total_distance, [0.75, 0.75, 0.75])]


        gauge = gauge_class(x, y, w=w, label="{val:.1f}", dummy_label="0.0", caption=f" / {total_distance:.1f} {suffix}",
                            data_range=colors)
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.interpolators['distance'](t) / 1000
        if self.units == 'imperial':
            value = km_to_mi(value)
        self.gauge.render(context, value)


class MapWidget:
    def __init__(self, data_source, x, y, h, style='map'):
        self.data_source = data_source
        gauge_class = STYLE_TABLE[style]
        gauge = gauge_class(x, y, h=h)
        # prerender
        gauge.prerender(self.data_source.fields['position_lat'], self.data_source.fields['position_long'])
        self.gauge = gauge

    def render(self, context, t):
        self.gauge.render(context, self.data_source.lat(t), self.data_source.lon(t))


class ElevationWidget:
    def __init__(self, data_source, x, y, h, style='grade', units='imperial'):
        self.data_source = data_source
        self.units = units
        gauge_class = STYLE_TABLE[style]
        gauge = gauge_class(x, y, h=h, dist_scale=10 * 1000)
        # prerender
        gauge.prerender(self.data_source.fields['distance'], self.data_source.fields['altitude'])
        self.gauge = gauge

    def render(self, context, t):
        d = self.data_source.distance(t)
        if self.units == 'imperial':
            d = km_to_mi(d)
        self.gauge.render(context, d, self.data_source.altitude(t), self.data_source.grade(t))
