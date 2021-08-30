import logging
import math

import cairo
import numpy as np

from .utils import *
from ..utils import *
from ..globals import globals
from .text import Text

logger = logging.getLogger(__name__)

class GaugeMap:
    def __init__(self, x, y, w = 400, h = 400, line_width = 5, dot_size = 15):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.line_width = line_width
        self.dot_size = dot_size

        self.padding = w / 15

        self.bgpattern = make_background_pattern(0, self.y, 0, self.y + self.h)

        self.mapsurface = cairo.ImageSurface(cairo.Format.A8, w, h)

        self.minx, self.maxx = self.x + self.padding, self.x + self.w - self.padding
        self.miny, self.maxy = self.y + self.padding, self.y + self.h - self.padding

    def prerender(self, latdata, londata):
        logger.debug("... computing map bounds ...")

        # Determine the bounds.
        self.minlat, self.maxlat = math.inf, -math.inf
        self.minlon, self.maxlon = math.inf, -math.inf

        for (tm, lat) in latdata:
            if lat < self.minlat:
                self.minlat = lat
            if lat > self.maxlat:
                self.maxlat = lat
        ctrlat = (self.minlat + self.maxlat) / 2

        for (tm, lon) in londata:
            if lon < self.minlon:
                self.minlon = lon
            if lon > self.maxlon:
                self.maxlon = lon
        ctrlon = (self.minlon + self.maxlon) / 2

        # Meet the aspect ratio.
        if ((self.maxlon - self.minlon) / (self.maxlat - self.minlat)) < (self.w / self.h):
            lonh = (self.maxlat - self.minlat) * self.w / self.h
            self.minlon = ctrlon - lonh / 2
            self.maxlon = ctrlon + lonh / 2
        else:
            latw = (self.maxlon - self.minlon) * self.h / self.w
            self.minlat = ctrlat - latw / 2
            self.maxlat = ctrlat + latw / 2

        logger.debug(f"... rendering map on lat [{self.minlat}, {self.maxlat}], lon [{self.minlon}, {self.maxlon}] ...")
        ctx = cairo.Context(self.mapsurface)

        npts = 0
        for ((tm1, lat), (tm2, lon)) in zip(latdata, londata):
            if tm1 != tm2:
                raise ValueError("latdata and londata not aligned in map")
            x = lerp(self.minlon, self.padding, self.maxlon, self.w - self.padding, lon)
            y = lerp(self.minlat, self.h - self.padding, self.maxlat, self.padding, lat)
            ctx.line_to(x, y)

            npts += 1

        ctx.set_line_width(self.line_width)
        ctx.set_source_rgb(1.0, 1.0, 1.0)
        ctx.stroke()

        logger.debug(f"... rendered {npts} points ...")

    def render(self, ctx, lat, lon):
        if lat is None or lon is None:
            ctx.push_group()
            ctx.rectangle(self.x, self.y, self.w, self.h)
            ctx.set_source(self.bgpattern)
            ctx.fill()
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(0.9)
            return

        ctx.push_group()

        # paint a background
        ctx.rectangle(self.x, self.y, self.w, self.h)
        ctx.set_source(self.bgpattern)
        ctx.fill()

        # paint the map
        ctx.set_source_rgb(0.8, 0.8, 0.8)
        ctx.mask_surface(self.mapsurface, self.x, self.y)

        # paint a dot
        x = lerp(self.minlon, self.minx, self.maxlon, self.maxx, lon)
        y = lerp(self.minlat, self.maxy, self.maxlat, self.miny, lat)

        ctx.push_group()

        ctx.set_source_rgba(1.0, 1.0, 0.3, 0.5)
        ctx.arc(x, y, self.dot_size, 0, math.pi * 2)
        ctx.fill()

        ctx.set_source_rgb(1.0, 0.3, 0.3)
        ctx.arc(x, y, self.dot_size / 2, 0, math.pi * 2)
        ctx.fill()

        ctx.pop_group_to_source()
        ctx.paint_with_alpha(0.9)

        ctx.pop_group_to_source()
        ctx.paint_with_alpha(0.9)

class GaugeElevationMap:
    def __init__(self, x, y, w = 400, h = 400, line_width = 5, dot_size = 15, dist_scale = 10, with_grade = True, with_elev = True, units = None):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.line_width = line_width
        self.dot_size = dot_size
        self.dist_scale = dist_scale

        self.padding = w / 10

        self.bgpattern = make_background_pattern(0, self.y, 0, self.y + self.h)

        self.fgpattern = cairo.LinearGradient(self.x, 0, self.x + self.w, 0)
        self.fgpattern.add_color_stop_rgba(0.0,                         0.8, 0.8, 0.8, 0.0)
        self.fgpattern.add_color_stop_rgba(      self.padding / self.w, 0.8, 0.8, 0.8, 1.0)
        self.fgpattern.add_color_stop_rgba(1.0 - self.padding / self.w, 0.8, 0.8, 0.8, 1.0)
        self.fgpattern.add_color_stop_rgba(1.0,                         0.8, 0.8, 0.8, 0.0)

        self.minx, self.maxx = self.x + self.padding, self.x + self.w - self.padding
        self.miny, self.maxy = self.y + self.padding, self.y + self.h - self.padding

        if with_grade:
            self.grade_text = Text(self.x + self.padding / 3, self.y + self.h - self.padding / 3,
                                   size = self.h * 0.2,
                                   dropshadow = self.h * 0.03 if globals['style']['text_shadows'] else 0,
                                   halign = Text.HALIGN_LEFT, valign = Text.VALIGN_BOTTOM)

        if with_elev:
            self.elev_text = Text(self.x + self.padding / 3, self.y + self.h - self.padding / 3,
                                  size = self.h * 0.15,
                                  dropshadow = self.h * 0.03 if globals['style']['text_shadows'] else 0,
                                  halign = Text.HALIGN_CENTER, valign = Text.VALIGN_TOP,
                                  color = (0.8, 0.8, 0.8))

        self.units = globals['units'] if units is None else units

    def prerender(self, distdata, elevdata):
        logger.debug("... computing elevmap bounds ...")

        # Determine the bounds.
        self.mindist, self.maxdist = distdata[0][1], distdata[-1][1]
        self.minelev, self.maxelev = math.inf, -math.inf

        for (tm, elev) in elevdata:
            if elev < self.minelev:
                self.minelev = elev
            if elev > self.maxelev:
                self.maxelev = elev

        self.surfx = int((self.maxdist - self.mindist) / self.dist_scale * self.w)
        self.mapsurface = cairo.ImageSurface(cairo.Format.A8, self.surfx, int(self.y - self.padding * 2))

        logger.debug(f"... rendering elevmap ...")
        ctx = cairo.Context(self.mapsurface)

        npts = 0
        distp = 0
        elevp = 0
        while distp < len(distdata) and elevp < len(elevdata):
            # align distance and elevation data, skipping samples for which there is no match
            tmd, dist = distdata[distp]
            tme, elev = elevdata[elevp]
            if tmd < tme:
                distp += 1
                continue
            if tme < tmd:
                elevp += 1
                continue

            x = lerp(self.mindist, 0, self.maxdist, self.surfx, dist)
            y = lerp(self.minelev, self.h - self.padding, self.maxelev, self.padding, elev)
            ctx.line_to(x, y)

            distp += 1
            elevp += 1
            npts += 1

        ctx.set_line_width(self.line_width)
        ctx.set_source_rgb(1.0, 1.0, 1.0)
        ctx.stroke()

        logger.debug(f"... rendered {npts} points ...")

    def render(self, ctx, dist, elev, grade):
        if dist is None or elev is None:
            ctx.push_group()
            ctx.rectangle(self.x, self.y, self.w, self.h)
            ctx.set_source(self.bgpattern)
            ctx.fill()
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(0.9)
            return

        ctx.push_group()

        # paint a background
        ctx.rectangle(self.x, self.y, self.w, self.h)
        ctx.set_source(self.bgpattern)
        ctx.fill()

        # paint the map
        # XXX: clamp map position to [0, self.surfx]
        ctx.save()
        ctx.rectangle(self.x, self.y, self.w, self.h)
        ctx.clip()
        ctx.set_source(self.fgpattern)
        ctx.mask_surface(self.mapsurface, self.x - dist / self.dist_scale * self.w + self.w / 2, self.y)
        ctx.restore()

        # paint a dot
        x = self.x + self.w / 2
        y = lerp(self.minelev, self.y + self.h - self.padding, self.maxelev, self.y + self.padding, elev)

        ctx.push_group()

        ctx.set_source_rgba(1.0, 1.0, 0.3, 0.5)
        ctx.arc(x, y, self.dot_size, 0, math.pi * 2)
        ctx.fill()

        ctx.set_source_rgb(1.0, 0.3, 0.3)
        ctx.arc(x, y, self.dot_size / 2, 0, math.pi * 2)
        ctx.fill()

        ctx.pop_group_to_source()
        ctx.paint_with_alpha(0.9)

        if self.grade_text and grade is not False and not np.isnan(grade):
            grade_hue = lerp(-5, 0.5, 10, 0.0, grade)
            self.grade_text.color = colorsys.hsv_to_rgb(grade_hue, 0.4, 0.9)
            self.grade_text.render(ctx, f"{grade:.1f}%")

        elev_ft = m_to_ft(elev)
        if self.elev_text:
            self.elev_text.x = x
            self.elev_text.y = y + self.dot_size * 1.3
            self.elev_text.render(ctx, f"{elev_ft:.0f}ft" if self.units == 'imperial' else f"{elev:.0f}m")

        ctx.pop_group_to_source()
        ctx.paint_with_alpha(0.9)
