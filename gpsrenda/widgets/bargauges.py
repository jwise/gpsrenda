import colorsys

import cairo
import numpy

from .utils import *
from .text import Text
from ..globals import globals


DEFAULT_RGB = (0.4, 0.4, 1.0)


class GaugeHorizontal:
    def __init__(self, x, y, w=600, h=60, label='{val:.0f}', dummy_label='99.9', caption='', dummy_caption='mph',
                 data_range=[0, 100], gradient=None, markers={}):
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
                                 dropshadow = self.h * 0.1 if globals['style']['text_shadows'] else 0,
                                 halign = Text.HALIGN_LEFT, valign = Text.VALIGN_BOTTOM_DESCENDERS)
        self.caption_text.x -= self.caption_text.measure(dummy_caption).width + self.caption_text.dropshadow

        self.label_text = Text(self.caption_text.x - self.padding / 2,
                               self.caption_text.y - self.caption_text.descender_y - self.caption_text.dropshadow,
                               face = Text.DEFAULT_MONO_FONT,
                               size = self.h * 0.9,
                               #slant = cairo.FontSlant.ITALIC,
                               dropshadow = self.h * 0.1 if globals['style']['text_shadows'] else 0,
                               halign = Text.HALIGN_RIGHT, valign = Text.VALIGN_BASELINE)

        self.gaugew = self.label_text.x - self.label_text.measure(dummy_label).x_advance - self.padding * 3 - self.x

        if isinstance(data_range, dict):
            self.data_range = [(k, v) for (k, v) in data_range.items()]
        elif isinstance(data_range, list):
            self.data_range = [(data_range[0], DEFAULT_RGB),
                               (data_range[-1], DEFAULT_RGB)]
        else:
            raise ValueError("`data_range` must be a dictionary or list")

        self.min = self.data_range[0][0]
        self.max = self.data_range[-1][0]

        self.show_gradient = globals['style']['bar_gradients'] if gradient is None else gradient
        self.gradient_tint = globals['style']['bar_gradients_tint']
        self.gradient = HSVGradient(self.x + self.padding, 0, self.x + self.padding + self.gaugew, 0, self.data_range)

        self.bgpattern = make_background_pattern(0, self.y, 0, self.y + self.h)

        self.markers = markers

    def render(self, ctx, val):
        if (val is None) or np.isnan(val):
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
        cur_rgb = self.gradient.lookup(val)
        cur_hsv = colorsys.rgb_to_hsv(*cur_rgb)
        ctx.rectangle(self.x + self.padding, self.y + self.padding, lerp(self.min, 0, self.max, self.gaugew, val),
                      self.h - self.padding * 2)

        if self.show_gradient:
            ctx.set_source(self.gradient.pattern)
            ctx.fill()

            ctx.rectangle(self.x + self.padding, self.y + self.padding, lerp(self.min, 0, self.max, self.gaugew, val),
                          self.h - self.padding * 2)
            ctx.set_source_rgba(cur_rgb[0], cur_rgb[1], cur_rgb[2], self.gradient_tint)
        else:
            ctx.set_source_rgb(*cur_rgb)

        ctx.fill()

        # paint any markers
        for marker_name, marker_value in self.markers.items():
            # line
            ctx.set_source_rgb(1.0, 1.0, 1.0)
            ctx.set_line_width(4)
            xpos = lerp(self.min, 0, self.max, self.gaugew, marker_value)
            ctx.move_to(xpos, self.y + self.padding)
            ctx.line_to(xpos, self.y + self.h - self.padding)
            ctx.stroke()

            # text
            marker_text = Text(xpos + 8,
                               self.y + self.h / 2,
                               face=Text.DEFAULT_MONO_FONT,
                               size=self.h * 0.5,
                               dropshadow= self.h * 0.03 if globals['style']['text_shadows'] else 0,
                               halign=Text.HALIGN_LEFT,
                               valign=Text.VALIGN_CENTER)
            marker_text.render(ctx, marker_name)

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
    def __init__(self, x, y, w=80, h=400, label='{val:.0f}°F', dummy_label='100°F', data_range=[0, 100],
                 gradient=False):
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

        if isinstance(data_range, dict):
            self.data_range = [(k, v) for (k, v) in data_range.items()]
        elif isinstance(data_range, list):
            self.data_range = [(data_range[0], DEFAULT_RGB),
                               (data_range[-1], DEFAULT_RGB)]
        else:
            raise ValueError("`data_range` must be a dictionary or list")

        self.min = self.data_range[0][0]
        self.max = self.data_range[-1][0]

        self.show_gradient = globals['style']['bar_gradients'] if gradient is None else gradient
        self.gradient_tint = globals['style']['bar_gradients_tint']
        self.gradient = HSVGradient(0, self.y + self.padding + self.gaugeh, 0, self.y + self.padding, self.data_range)

        self.bgpattern = make_background_pattern(0, self.y, 0, self.y + self.h)

    def render(self, ctx, val):
        if (val is None) or np.isnan(val):
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
        cur_rgb = self.gradient.lookup(val)
        cur_hsv = colorsys.rgb_to_hsv(*cur_rgb)
        ctx.rectangle(self.x + self.padding, self.y + self.padding + self.gaugeh, self.w - self.padding * 2, -lerp(self.min, 0, self.max, self.gaugeh, val))
        if self.show_gradient:
            ctx.set_source(self.gradient.pattern)
            ctx.fill()

            ctx.rectangle(self.x + self.padding, self.y + self.padding, lerp(self.min, 0, self.max, self.gaugew, val),
                          self.h - self.padding * 2)
            ctx.set_source_rgba(cur_rgb[0], cur_rgb[1], cur_rgb[2], self.gradient_tint)
        else:
            ctx.set_source_rgb(*cur_rgb)
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
