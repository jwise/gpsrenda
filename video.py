import sys
import numpy as np
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('GstBase', '1.0')
from gi.repository import Gst, GstApp, GstBase, GLib, GObject
import cairo
import time
import logging
from ctypes import *
import struct
import os
import datetime
import colorsys
import math

import fit
from gst_hacks import map_gst_buffer

Gst.init(sys.argv)

# start
#FILE='/home/joshua/gopro/20210605-copperopolis/GX010026.MP4'
#SEEKTIME=140

# robin
#FILE='/home/joshua/gopro/20210605-copperopolis/GX010037.MP4'
#SEEKTIME=0

# descent
FILE='/home/joshua/gopro/20210605-copperopolis/GX010031.MP4'
SEEKTIME=0

FRAMERATE=30000/1001
FITFILE='/home/joshua/gopro/20210605-copperopolis/Copperopolis_Road_Race_off_the_back_7_19_but_at_least_I_didn_t_DNF_.fit'
TIMEFUDGE=36.58
FLIP=True

# Load the timecode.  XXX: is there a better way to do this?
TMCD_OUT='tmp_tmcd'
os.system(f"ffmpeg -i {FILE} -map 0:d:0 -y -f data {TMCD_OUT}")
with open(TMCD_OUT, "rb") as f:
    tmcd_frames = struct.unpack(">I", f.read())[0]
tmcd_secs = tmcd_frames / FRAMERATE
print(tmcd_secs)
start_time = datetime.datetime(year = 2021, month = 6, day = 5) + datetime.timedelta(seconds = tmcd_secs) # this is LOCAL TIME

start_time += datetime.timedelta(hours = 7)
start_time += datetime.timedelta(seconds = -TIMEFUDGE)

f = fit.FitByTime(FITFILE)

def lerp(x0, v0, x1, v1, x):
    if x < x0:
        return v0
    if x > x1:
        return v1
    alpha = (x - x0) / (x1 - x0)
    return v0 * (1.0 - alpha) + v1 * alpha

class Text:
    VALIGN_TOP = "TOP"
    VALIGN_BASELINE = "BASELINE"
    VALIGN_BOTTOM_DESCENDERS = "BOTTOM_DESCENDERS"
    VALIGN_BOTTOM = "BOTTOM"
    HALIGN_LEFT = "LEFT"
    HALIGN_CENTER = "CENTER"
    HALIGN_RIGHT = "RIGHT"
    
    DEFAULT_FONT = "Ubuntu"
    DEFAULT_MONO_FONT = "Ubuntu Mono"
    
    def __init__(self, x, y, color = (1.0, 1.0, 1.0), face = DEFAULT_FONT, slant = cairo.FontSlant.NORMAL, weight = cairo.FontWeight.BOLD, halign = HALIGN_LEFT, valign = VALIGN_TOP, size = 12, dropshadow = 0, dropshadow_color = (0.0, 0.0, 0.0)):
        self.font = cairo.ToyFontFace(face, slant, weight)
        self.size = size
        self.x = x
        self.y = y
        self.color = color
        self.halign = halign
        self.valign = valign
        self.dropshadow = dropshadow
        self.dropshadow_color = dropshadow_color
        
        self.scaledfont = cairo.ScaledFont(self.font, cairo.Matrix(xx = size, yy = size), cairo.Matrix(), cairo.FontOptions())
        
        descender = self.measure('pqfj')
        self.descender_y = descender.height + descender.y_bearing
    
    def measure(self, text):
        # mostly useful: x_bearing, y_bearing, width, height
        return self.scaledfont.text_extents(text)
        
    def render(self, ctx, text):
        exts = self.measure(text)
        
        x = self.x
        y = self.y
        
        if self.halign == Text.HALIGN_LEFT:
            x = x - exts.x_bearing
        elif self.halign == Text.HALIGN_CENTER:
            x = x - exts.x_bearing - (exts.width + self.dropshadow) / 2
        elif self.halign == Text.HALIGN_RIGHT:
            x = x - exts.x_advance - self.dropshadow
        else:
            raise ValueError(f"invalid halign {self.halign}")
        
        if self.valign == Text.VALIGN_TOP:
            y = y - exts.y_bearing
        elif self.valign == Text.VALIGN_BOTTOM:
            y = y - (exts.height + exts.y_bearing) - self.dropshadow
        elif self.valign == Text.VALIGN_BOTTOM_DESCENDERS:
            y = y - self.descender_y - self.dropshadow
        elif self.valign == Text.VALIGN_BASELINE:
            pass
        else:
            raise ValueError(f"invalid valign {self.valign}")
        
        ctx.set_scaled_font(self.scaledfont)
        
        if self.dropshadow != 0:
            ctx.set_source_rgb(*self.dropshadow_color)
            ctx.move_to(x + self.dropshadow, y + self.dropshadow)
            ctx.show_text(text)
        
        ctx.set_source_rgb(*self.color)
        ctx.move_to(x, y)
        ctx.show_text(text)

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

class GaugeHorizontal:
    def __init__(self, x, y, w = 600, h = 60, label = '{val:.0f}', dummy_label = '99.9', caption = '', dummy_caption = 'mph', data_range = [(0, (1.0, 0, 0)), (100, (1.0, 0, 0))]):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.label = label
        self.caption = caption
        
        self.padding = h / 8

        if dummy_caption == None:
            dummy_caption = caption
        self.caption_text = Text(self.x + self.w - self.padding / 2,
                                 self.y + self.h - self.padding,
                                 size = self.h * 0.5,
                                 dropshadow = self.h * 0.1,
                                 halign = Text.HALIGN_LEFT, valign = Text.VALIGN_BOTTOM_DESCENDERS)
        self.caption_text.x -= self.caption_text.measure(dummy_caption).width + self.caption_text.dropshadow
        
        self.label_text = Text(self.caption_text.x - self.padding / 2,
                               self.caption_text.y - self.caption_text.descender_y - self.caption_text.dropshadow,
                               face = Text.DEFAULT_MONO_FONT,
                               size = self.h * 0.9,
                               #slant = cairo.FontSlant.ITALIC,
                               dropshadow = self.h * 0.1,
                               halign = Text.HALIGN_RIGHT, valign = Text.VALIGN_BASELINE)
        
        self.gaugew = self.label_text.x - self.label_text.measure(dummy_label).x_advance - self.padding * 3 - self.x
        
        self.min = data_range[0][0]
        self.max = data_range[-1][0]
        
        self.data_range = data_range
        
        self.gradient = HSVGradient(self.x + self.padding, 0, self.x + self.padding + self.gaugew, 0, data_range)
        
        self.bgpattern = cairo.LinearGradient(0, self.y, 0, self.y + self.h)
        self.bgpattern.add_color_stop_rgba(0.0, 0.2, 0.2, 0.2, 0.9)
        self.bgpattern.add_color_stop_rgba(1.0, 0.4, 0.4, 0.4, 0.9)
    
    def render(self, ctx, val):
        if val is None:
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
        
        # paint the gauge bar itself
        ctx.rectangle(self.x + self.padding, self.y + self.padding, lerp(self.min, 0, self.max, self.gaugew, val), self.h - self.padding * 2)
        ctx.set_source(self.gradient.pattern)
        ctx.fill()

        cur_rgb = self.gradient.lookup(val)
        cur_hsv = colorsys.rgb_to_hsv(*cur_rgb)
        
        # paint a semitransparent overlay on the gauge bar to colorize it
        # for where we are in the scale
        ctx.rectangle(self.x + self.padding, self.y + self.padding, lerp(self.min, 0, self.max, self.gaugew, val), self.h - self.padding * 2)
        ctx.set_source_rgba(cur_rgb[0], cur_rgb[1], cur_rgb[2], 0.4)
        ctx.fill()

        # paint the surround for the gauge cluster
        ctx.rectangle(self.x + self.padding, self.y + self.padding, self.gaugew, self.h - self.padding * 2)
        ctx.set_line_width(4)
        ctx.set_source_rgb(0, 0, 0)
        ctx.stroke()
        
        # render the big numbers
        text = self.label.format(val = val)
        self.label_text.color = colorsys.hsv_to_rgb(cur_hsv[0], 0.1, 1.0)
        self.label_text.render(ctx, text)

        self.caption_text.render(ctx, self.caption)
        
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(0.9)

class GaugeVertical:
    def __init__(self, x, y, w = 80, h = 400, label = '{val:.0f}°F', dummy_label = '100°F', data_range = [(70, (1.0, 0, 0)), (100, (1.0, 0, 0))]):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.label = label
        
        self.padding = w / 8

        self.label_text = Text(self.x + self.w / 2,
                               self.y + self.h - self.padding,
                               face = Text.DEFAULT_FONT,
                               size = self.w * 0.4,
                               dropshadow = self.w * 0.05,
                               halign = Text.HALIGN_CENTER, valign = Text.VALIGN_BASELINE)
        
        self.gaugeh = self.h - self.label_text.measure(dummy_label).height - self.padding * 3
        
        self.min = data_range[0][0]
        self.max = data_range[-1][0]
        
        self.data_range = data_range
        
        self.gradient = HSVGradient(0, self.y + self.padding + self.gaugeh, 0, self.y + self.padding, data_range)
        
        self.bgpattern = cairo.LinearGradient(0, self.y, 0, self.y + self.h)
        self.bgpattern.add_color_stop_rgba(0.0, 0.2, 0.2, 0.2, 0.9)
        self.bgpattern.add_color_stop_rgba(1.0, 0.4, 0.4, 0.4, 0.9)
    
    def render(self, ctx, val):
        if val is None:
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
        
        # paint the gauge bar itself
        ctx.rectangle(self.x + self.padding, self.y + self.padding + self.gaugeh, self.w - self.padding * 2, -lerp(self.min, 0, self.max, self.gaugeh, val))
        ctx.set_source(self.gradient.pattern)
        ctx.fill()

        cur_rgb = self.gradient.lookup(val)
        cur_hsv = colorsys.rgb_to_hsv(*cur_rgb)
        
        # paint a semitransparent overlay on the gauge bar to colorize it
        # for where we are in the scale
        ctx.rectangle(self.x + self.padding, self.y + self.padding + self.gaugeh, self.w - self.padding * 2, -lerp(self.min, 0, self.max, self.gaugeh, val))
        ctx.set_source_rgba(cur_rgb[0], cur_rgb[1], cur_rgb[2], 0.4)
        ctx.fill()

        # paint the surround for the gauge cluster
        ctx.rectangle(self.x + self.padding, self.y + self.padding, self.w - self.padding * 2, self.gaugeh)
        ctx.set_line_width(4)
        ctx.set_source_rgb(0, 0, 0)
        ctx.stroke()
        
        # render the big numbers
        text = self.label.format(val = val)
        self.label_text.color = colorsys.hsv_to_rgb(cur_hsv[0], 0.1, 1.0)
        self.label_text.render(ctx, text)

        ctx.pop_group_to_source()
        ctx.paint_with_alpha(0.9)

class GaugeMap:
    def __init__(self, x, y, w = 400, h = 400, line_width = 5, dot_size = 15):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.line_width = line_width
        self.dot_size = dot_size
        
        self.padding = w / 15

        self.bgpattern = cairo.LinearGradient(0, self.y, 0, self.y + self.h)
        self.bgpattern.add_color_stop_rgba(0.0, 0.2, 0.2, 0.2, 0.9)
        self.bgpattern.add_color_stop_rgba(1.0, 0.4, 0.4, 0.4, 0.9)
        
        self.mapsurface = cairo.ImageSurface(cairo.Format.A8, w, h)
        
        self.minx, self.maxx = self.x + self.padding, self.x + self.w - self.padding
        self.miny, self.maxy = self.y + self.padding, self.y + self.h - self.padding
    
    def prerender(self, latdata, londata):
        print("...computing map bounds...")
        
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

        print(f"...rendering map on lat [{self.minlat}, {self.maxlat}], lon [{self.minlon}, {self.maxlon}]...")
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

        print(f"...rendered {npts} points...")
    
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
    def __init__(self, x, y, w = 400, h = 400, line_width = 5, dot_size = 15, dist_scale = 10, with_grade = True, with_elev = True):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.line_width = line_width
        self.dot_size = dot_size
        self.dist_scale = dist_scale
        
        self.padding = w / 10

        self.bgpattern = cairo.LinearGradient(0, self.y, 0, self.y + self.h)
        self.bgpattern.add_color_stop_rgba(0.0, 0.2, 0.2, 0.2, 0.9)
        self.bgpattern.add_color_stop_rgba(1.0, 0.4, 0.4, 0.4, 0.9)
        
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
                                   dropshadow = self.h * 0.03,
                                   halign = Text.HALIGN_LEFT, valign = Text.VALIGN_BOTTOM)

        if with_elev:
            self.elev_text = Text(self.x + self.padding / 3, self.y + self.h - self.padding / 3,
                                  size = self.h * 0.15,
                                  dropshadow = self.h * 0.03,
                                  halign = Text.HALIGN_CENTER, valign = Text.VALIGN_TOP,
                                  color = (0.8, 0.8, 0.8))
    
    def prerender(self, distdata, elevdata):
        print("...computing elevmap bounds...")
        
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
        
        print(f"...rendering elevmap...")
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

        print(f"...rendered {npts} points...")
    
    def render(self, ctx, dist, elev, grade):
        if dist is None or elev is None or grade is None:
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
        
        if self.grade_text:
            grade_hue = lerp(-5, 0.5, 10, 0.0, grade)
            self.grade_text.color = colorsys.hsv_to_rgb(grade_hue, 0.4, 0.9)
            self.grade_text.render(ctx, f"{grade:.1f}%")
        
        elev_ft = elev * 3.2808399
        if self.elev_text:
            self.elev_text.x = x
            self.elev_text.y = y + self.dot_size * 1.3
            self.elev_text.render(ctx, f"{elev_ft:.0f}ft")
        
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(0.9)

cadence_gauge    = GaugeHorizontal(30, 1080 - 30 - 65 * 1, label = '{val:.0f}', caption = 'rpm', data_range = [(75, (1.0, 0, 0)), (90, (0.0, 0.6, 0.0)), (100, (0.0, 0.6, 0.0)), (120, (1.0, 0.0, 0.0))])
heart_rate_gauge = GaugeHorizontal(30, 1080 - 30 - 65 * 2, label = '{val:.0f}', caption = 'bpm', data_range = [(120, (0, 0.6, 0)), (150, (0.2, 0.6, 0.0)), (180, (0.8, 0.0, 0.0))])
speed_gauge      = GaugeHorizontal(30, 1080 - 30 - 65 * 3, label = '{val:.1f}', caption = 'mph', data_range = [(8, (0.6, 0, 0)), (15, (0.0, 0.6, 0.0)), (30, (1.0, 0.0, 0.0))])
temp_gauge       = GaugeVertical  (1920 - 120, 30, data_range = [(60, (0.6, 0.6, 0.0)), (80, (0.6, 0.3, 0)), (100, (0.8, 0.0, 0.0))])
dist_total_mi    = f.fields['distance'][-1][1] * 0.62137119
dist_gauge       = GaugeHorizontal(30, 30, w = 1920 - 120 - 30 - 30, label = "{val:.1f}", dummy_label = "99.9", caption = f" / {dist_total_mi:.1f} miles", dummy_caption = None, data_range = [(0, (0.8, 0.7, 0.7)), (dist_total_mi, (0.7, 0.8, 0.7))])
map              = GaugeMap(1920 - 30 - 400, 1080 - 30 - 65 * 3, h = 65 * 3)
elevmap          = GaugeElevationMap(1920 - 30 - 400 - 30 - 400, 1080 - 30 - 65 * 3, h = 65 * 3)
map.prerender(f.fields['position_lat'], f.fields['position_long'])
elevmap.prerender(f.fields['distance'], f.fields['altitude'])

def paint(ctx, w, h, tm):
    cadence = f.lerp_value(tm, 'cadence', flatten_zeroes = datetime.timedelta(seconds = 2.0))
    cadence_gauge.render(ctx, cadence)
    
    heart_rate = f.lerp_value(tm, 'heart_rate')
    heart_rate_gauge.render(ctx, heart_rate)
    
    speed_kph = f.lerp_value(tm, 'speed')
    speed_mph = speed_kph * 0.62137119 if speed_kph is not None else None
    speed_gauge.render(ctx, speed_mph)
    
    temp_c = f.lerp_value(tm, 'temperature')
    temp_f = (temp_c * 9 / 5) + 32 if temp_c is not None else None
    temp_gauge.render(ctx, temp_f)
    
    dist_km = f.lerp_value(tm, 'distance')
    dist_mi = dist_km * 0.62137119 if dist_km is not None else None
    dist_gauge.render(ctx, dist_mi)
    
    latitude  = f.lerp_value(tm, 'position_lat')
    longitude = f.lerp_value(tm, 'position_long')
    map.render(ctx, latitude, longitude)
    
    altitude = f.lerp_value(tm, 'altitude')
    grade    = f.lerp_value(tm, 'grade')
    elevmap.render(ctx, dist_km, altitude, grade)

# https://github.com/jackersson/gst-overlay/blob/master/gst_overlay/gst_overlay_cairo.py
class GstOverlayGPS(GstBase.BaseTransform):
    __gstmetadata__ = ("GPS overlay object",
                       "video.py",
                       "GPS overlay",
                       "jwise")
    __gsttemplates__ = (Gst.PadTemplate.new("src",
                                            Gst.PadDirection.SRC,
                                            Gst.PadPresence.ALWAYS,
                                            Gst.Caps.from_string("video/x-raw,format=BGRA")),
                        Gst.PadTemplate.new("sink",
                                            Gst.PadDirection.SINK,
                                            Gst.PadPresence.ALWAYS,
                                            Gst.Caps.from_string("video/x-raw,format=BGRA")))
    def __init__(self):
        super(GstOverlayGPS, self).__init__()
    
    def do_transform_ip(self, buffer):
        tst = time.time()
        caps = self.srcpad.get_current_caps()
        h = caps.get_structure(0).get_value("height")
        w = caps.get_structure(0).get_value("width")
        
        with map_gst_buffer(buffer, Gst.MapFlags.READ) as data:
            surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h)
            ctx = cairo.Context(surf)
            paint(ctx, w, h, start_time + datetime.timedelta(seconds = self.segment.position / 1000000000))
        
        print(f"transform took {(time.time() - tst) * 1000:.1f}ms")
        
        return Gst.FlowReturn.OK


def register(plugin):
    return Gst.Element.register(plugin, 'gpsoverlay', 0, GObject.type_register(GstOverlayGPS))
if not Gst.Plugin.register_static(Gst.VERSION_MAJOR, Gst.VERSION_MINOR, 'gpsoverlay', 'GPS overlay object', register, '0.0', 'unknown', 'gstreamer', 'gpsrenda', 'the.internet'):
    raise ImportError("failed to register gpsoverlay with gstreamer")
                                                                                        
pipeline = Gst.parse_launch(
    f"filesrc location={FILE} ! decodebin name=decoder "
    f"decoder. ! queue ! audioconvert ! audioresample ! alsasink "
    f"decoder. ! queue ! videoconvert ! " +
    ("videoflip method=rotate-180 ! " if FLIP else "") +
    f"gpsoverlay ! videoconvert ! queue ! "
    f"autovideosink"
    )


loop = GLib.MainLoop()

did_seek = False

def on_message(bus, message, pipeline, loop):
    global did_seek
    
    mtype = message.type
    if mtype == Gst.MessageType.STATE_CHANGED:
        old_state, new_state, pending_state = message.parse_state_changed()
        print(f"pipeline state: {Gst.Element.state_get_name(old_state)} -> {Gst.Element.state_get_name(new_state)}")
        
        if new_state == Gst.State.PLAYING:
            q = Gst.Query.new_seeking(Gst.Format.TIME)
            pipeline.query(q)
            fmt, seek_enabled, start, end = q.parse_seeking()
            print(f"seek_enabled {seek_enabled}")
            
            if not did_seek:
                pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, SEEKTIME * Gst.SECOND) 
                did_seek = True

    if mtype == Gst.MessageType.EOS:
        print("EOS")
        loop.quit()
    elif mtype == Gst.MessageType.ERROR:
        print("Error!")
    elif mtype == Gst.MessageType.WARNING:
        print("Warning!")
    else:
        print(mtype)
    return True

bus = pipeline.get_bus()
bus.connect("message", on_message, pipeline, loop)
bus.add_signal_watch()

pipeline.set_state(Gst.State.PLAYING)
pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 30 * Gst.SECOND) 

try:
    loop.run()
except:
    loop.quit()
