import math

from gpsrenda.widgets import *
from gpsrenda.utils import timestamp_to_seconds, seconds_to_timestamp, km_to_mi, c_to_f, m_to_ft
from gpsrenda.widgets.utils import latlondist
from ..globals import globals

STYLE_TABLE = {
    'hbar': GaugeHorizontal,
    'vbar': GaugeVertical,
    'map': GaugeMap,
    'grade': GaugeElevationMap,
    'text': GaugeText,
}

def _dummy_value(n):
    return n if globals['style']['padding_strings']['dummy_value'] is None else globals['style']['padding_strings']['dummy_value']

class SpeedWidget:
    def __init__(self, data_source, x, y, style='hbar', units=None, data_range=[0, 50], **kwargs):
        self.data_source = data_source
        self.units = globals['units'] if units is None else units
        gauge_class = STYLE_TABLE[style]
        caption = 'mph' if self.units == 'imperial' else 'kph'

        gauge = gauge_class(x, y, label="{val:.1f}", dummy_label=_dummy_value("99.9"), dummy_caption=globals['style']['padding_strings']['dummy_caption'], caption=caption, data_range=data_range, **kwargs)
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.speed(t) * 60 * 60 / 1000
        if self.units == 'imperial':
            value = km_to_mi(value)
        self.gauge.render(context, value)


class CadenceWidget:
    def __init__(self, data_source, x, y, style='hbar', data_range=[60, 120], **kwargs):
        self.data_source = data_source
        gauge_class = STYLE_TABLE[style]
        gauge = gauge_class(x, y, label="{val:.0f}", dummy_label=_dummy_value("999"), dummy_caption=globals['style']['padding_strings']['dummy_caption'], caption="rpm", data_range=data_range, **kwargs)
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.cadence(t)
        self.gauge.render(context, value)


class HeartRateWidget:
    def __init__(self, data_source, x, y, style='hbar', data_range=[40, 220], **kwargs):
        self.data_source = data_source
        gauge_class = STYLE_TABLE[style]
        gauge = gauge_class(x, y, label="{val:.0f}", dummy_label=_dummy_value("999"), dummy_caption=globals['style']['padding_strings']['dummy_caption'], caption="bpm", data_range=data_range, **kwargs)
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.heart_rate(t)
        self.gauge.render(context, value)


class PowerWidget:
    def __init__(self, data_source, x, y, style='hbar', data_range=[0, 1000], as_percent_ftp = None, markers={}, **kwargs):
        self.data_source = data_source
        gauge_class = STYLE_TABLE[style]
        gauge = gauge_class(x, y,
                            label="{val:.0f}", dummy_label=_dummy_value("999"),
                            dummy_caption=globals['style']['padding_strings']['dummy_caption'], caption="%FTP" if as_percent_ftp is not None else "W",
                            data_range=data_range, markers=markers,
                            **kwargs)
        self.norm_coeff = 1 if as_percent_ftp is None else (as_percent_ftp / 100.0)
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.power(t) / self.norm_coeff
        self.gauge.render(context, value)


class TemperatureWidget:
    def __init__(self, data_source, x, y, w=80, h=400, style='vbar', units=None, data_range=[0, 100], **kwargs):
        self.data_source = data_source
        self.units = globals['units'] if units is None else units
        gauge_class = STYLE_TABLE[style]
        suffix = '°F' if self.units == 'imperial' else '°C'

        gauge = gauge_class(x, y, w=w, h=h, label="{val:.0f}"+suffix if style == 'vbar' else "{val:.0f}", caption = suffix, dummy_label="0.0", data_range=data_range, **kwargs)
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.temperature(t)
        if self.units == 'imperial':
            value = c_to_f(value)
        self.gauge.render(context, value)


class AscentWidget:
    def __init__(self, data_source, x, y, w, style='hbar', units=None, data_range = [0, 1]):
        self.data_source = data_source
        self.units = globals['units'] if units is None else units
        gauge_class = STYLE_TABLE[style]
        suffix = 'ft' if self.units == 'imperial' else 'm'

        total_ascent = data_source.fields['ascent'][-1][1]

        if self.units == 'imperial':
            total_ascent = m_to_ft(total_ascent)

        if isinstance(data_range, dict):
            data_range = { v * total_ascent: rgb for v, rgb in data_range.items() }
        elif isinstance(data_range, list):
            data_range = [ v * total_ascent for v in data_range ]
        else:
          raise ValueError("`data_range` must be a dictionary or list")

        gauge = gauge_class(x, y, w=w, label="{val:.0f}", dummy_label=f"{total_ascent:.0f}",
                            caption=f" / {total_ascent:.0f} {suffix}", dummy_caption=None,
                            data_range=data_range)
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.ascent(t)
        if self.units == 'imperial':
            value = m_to_ft(value)
        self.gauge.render(context, value)


class DistanceWidget:
    def __init__(self, data_source, x, y, w, style='hbar', units=None, data_range = [0, 1]):
        self.data_source = data_source
        self.units = globals['units'] if units is None else units
        gauge_class = STYLE_TABLE[style]
        suffix = 'mi' if self.units == 'imperial' else 'km'

        total_distance = data_source.fields['distance'][-1][1] / 1000

        if self.units == 'imperial':
            total_distance = km_to_mi(total_distance)

        if isinstance(data_range, dict):
            data_range = { v * total_distance: rgb for v, rgb in data_range.items() }
        elif isinstance(data_range, list):
            data_range = [ v * total_distance for v in data_range ]
        else:
          raise ValueError("`data_range` must be a dictionary or list")

        gauge = gauge_class(x, y, w=w, label="{val:.1f}", dummy_label=f"{total_distance:.1f}",
                            caption=f" / {total_distance:.1f} {suffix}", dummy_caption=None,
                            data_range=data_range)
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.distance(t) / 1000
        if self.units == 'imperial':
            value = km_to_mi(value)
        self.gauge.render(context, value)

class DistanceRemainingWidget:
    def __init__(self, data_source, x, y, w, h=60, style='text', distance_past_end = 0, align_right = True):
        # Distance remaining is always in meters.  Sorry, that's how bikes
        # are.  I don't make the rules.
        self.data_source = data_source
        gauge_class = STYLE_TABLE[style]
        suffix = 'm'

        self.total_distance = data_source.fields['distance'][-1][1] - distance_past_end

        gauge = gauge_class(x, y, w=w, h=h, dummy_label=f"{self.total_distance:.0f}", caption = "m to go", italic = False, align_right = align_right)
        self.gauge = gauge

    def render(self, context, t):
        dist = self.data_source.distance(t)
        if dist is None or math.isnan(dist):
            self.gauge.render(context, None)
            return
        value = self.total_distance - dist
        if value < 0:
            value = 0
        self.gauge.render(context, f"{value:.0f}")

class MapWidget:
    PRIVACY_RANGE = 2000 #m

    def __init__(self, data_source, x, y, h, w=300, style='map', privacy=True):
        self.data_source = data_source
        self.privacy = privacy
        gauge_class = STYLE_TABLE[style]
        gauge = gauge_class(x, y, h=h, w=w)
        self.gauge = gauge
        # prerender
        self.prerender()

    def render(self, context, t):
        self.gauge.render(context, self.data_source.lat(t), self.data_source.lon(t))

    def prerender(self):
        lats, lons = self.data_source.fields['position_lat'], self.data_source.fields['position_long']

        if self.privacy:
            # Clear start and end points in a 2km radius of the finishing point
            endpoint = lats[-1][1] / 2**32 * 360, lons[-1][1] / 2**32 * 360

            start_idx = 0
            end_idx = len(lats) - 1

            for idx, (t, coord) in enumerate(zip(lats, lons)):
                coord = [coord[i] / 2**32 * 360 for i in range(2)]
                if latlondist(endpoint, coord) > MapWidget.PRIVACY_RANGE:
                    start_idx = idx
                    break

            for inv_idx, (t, coord) in enumerate(zip(lats[:-1], lons[::-1])):
                coord = [coord[i] / 2**32 * 360 for i in range(2)]
                if latlondist(endpoint, coord) > MapWidget.PRIVACY_RANGE:
                    end_idx = len(lats) - inv_idx - 1
                    break

            lats = lats[start_idx:end_idx]
            lons = lons[start_idx:end_idx]

        self.gauge.prerender(lats, lons)


class ElevationWidget:
    def __init__(self, data_source, x, y, w = 400, h = 400, style='grade', dist_scale = 10 * 1000, units=None, **kwargs):
        self.data_source = data_source
        self.units = globals['units'] if units is None else units
        gauge_class = STYLE_TABLE[style]
        gauge = gauge_class(x, y, w=w, h=h, dist_scale=dist_scale, units=units, **kwargs)
        # prerender
        gauge.prerender(self.data_source.fields['distance'], self.data_source.fields['altitude'])
        self.gauge = gauge

    def render(self, context, t):
        d = self.data_source.distance(t)
        self.gauge.render(context, d, self.data_source.altitude(t), self.data_source.grade(t))


class TimeWidget:
    def __init__(self, data_source, x, y, w, style='text'):
        import tzlocal

        self.data_source = data_source
        gauge_class = STYLE_TABLE[style]
        self.gauge = gauge_class(x, y, w=w, dummy_label = '00:00')
        self.tz = tzlocal.get_localzone()

    def render(self, context, t):
        ts = seconds_to_timestamp(t).astimezone(self.tz)
        self.gauge.render(context, f"{ts.hour:02}:{ts.minute:02}")

class TextWidget:
    def __init__(self, data_source, x, y, w = None, style='text', text='lol?'):
        import tzlocal

        self.data_source = data_source
        gauge_class = STYLE_TABLE[style]
        self.text = text
        self.gauge = gauge_class(x, y, w=w, dummy_label = text)

    def render(self, context, t):
        self.gauge.render(context, self.text)
