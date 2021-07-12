from importlib import import_module

from gpsrenda.utils import timestamp_to_seconds

class SpeedWidget:
    def __init__(self, data_source, x, y, style=None, units='metric'):
        self.data_source = data_source
        gauge_module = import_module('gpsrenda.widgets')
        gauge_class = getattr(gauge_module, style)
        gauge = gauge_class(x, y, label="{val:.0f}", dummy_label="0.0", caption="mph",
                            data_range=[(0, (1.0, 0, 0)), (100, (1.0, 0, 0))])
        self.gauge = gauge

    def render(self, context, t):
        value = self.data_source.interpolators['speed'](t)
        self.gauge.render(context, value)
