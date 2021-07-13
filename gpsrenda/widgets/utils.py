import cairo
import colorsys
import numpy as np

def lerp(x0, v0, x1, v1, x):
    if x < x0:
        return v0
    if x > x1:
        return v1
    alpha = (x - x0) / (x1 - x0)
    return v0 * (1.0 - alpha) + v1 * alpha

def latlondist(coord1, coord2):
    R = 6373.0
    lat1 = np.deg2rad(coord1[0])
    lat2 = np.deg2rad(coord2[0])
    lon1 = np.deg2rad(coord1[1])
    lon2 = np.deg2rad(coord2[1])
    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    dist = R * c

    return dist

# Cairo does not have a HSV gradient, so we make our own to interpolate the
# colors of the gauges.
class HSVGradient:
    def __init__(self, x0, y0, x1, y1, data_range):
        self.pattern = cairo.LinearGradient(x0, y0, x1, y1)

        self.min = data_range[0][0]
        self.max = data_range[-1][0]
        self.data_range = data_range

        self.pattern.add_color_stop_rgb(0.0, data_range[0][1][0], data_range[0][1][1], data_range[0][1][2])
        last = (0.0, data_range[0][1])
        for v in data_range[1:]:
            last_hsv = colorsys.rgb_to_hsv(*last[1])
            this_hsv = colorsys.rgb_to_hsv(*v[1])
            v = (lerp(self.min, 0.0, self.max, 1.0, v[0]), v[1])

            SUBSTOPS = 20
            for p in range(SUBSTOPS):
                # This is hokey, and does not interpolate 'the short way'
                # around the hue circle.  But it does interpolate correctly
                # from red to green, so ...
                rgb = colorsys.hsv_to_rgb(lerp(0, last_hsv[0], SUBSTOPS - 1, this_hsv[0], p),
                                          lerp(0, last_hsv[1], SUBSTOPS - 1, this_hsv[1], p),
                                          lerp(0, last_hsv[2], SUBSTOPS - 1, this_hsv[2], p))
                self.pattern.add_color_stop_rgb(lerp(0, last[0], SUBSTOPS - 1, v[0], p), rgb[0], rgb[1], rgb[2])

            last = v

    def lookup(self, val):
        # grumble: there's no easy way to look up a point in a pattern.  but
        # we want to know the current color!  at least it is slightly easier
        # than the HSV shenanigans above...
        last = self.data_range[0]
        this = self.data_range[0]
        for this in self.data_range[1:]:
            if this[0] >= val:
                break
            last = this
        last_hsv = colorsys.rgb_to_hsv(*last[1])
        this_hsv = colorsys.rgb_to_hsv(*this[1])
        cur_hsv = (lerp(last[0], last_hsv[0], this[0], this_hsv[0], val),
                   lerp(last[0], last_hsv[1], this[0], this_hsv[1], val),
                   lerp(last[0], last_hsv[2], this[0], this_hsv[2], val))
        return colorsys.hsv_to_rgb(*cur_hsv)
