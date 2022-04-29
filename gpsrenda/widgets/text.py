import cairo
from .utils import *
from ..globals import globals

class Text:
    VALIGN_TOP = "TOP"
    VALIGN_BASELINE = "BASELINE"
    VALIGN_BOTTOM_DESCENDERS = "BOTTOM_DESCENDERS"
    VALIGN_BOTTOM = "BOTTOM"
    VALIGN_CENTER = "CENTER"
    HALIGN_LEFT = "LEFT"
    HALIGN_CENTER = "CENTER"
    HALIGN_RIGHT = "RIGHT"

    DEFAULT_FONT = "__DEFAULT_FONT__"
    DEFAULT_MONO_FONT = "__DEFAULT_MONO_FONT__"

    def __init__(self, x, y, color = (1.0, 1.0, 1.0), face = DEFAULT_FONT, slant = cairo.FontSlant.NORMAL, weight = cairo.FontWeight.BOLD, halign = HALIGN_LEFT, valign = VALIGN_TOP, size = 12, dropshadow = 0, dropshadow_color = (0.0, 0.0, 0.0)):
        if face == Text.DEFAULT_FONT:
            face = globals['style']['fonts']['proportional']
        elif face == Text.DEFAULT_MONO_FONT:
            face = globals['style']['fonts']['monospace']
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
        elif self.valign == Text.VALIGN_CENTER:
            y = y - exts.y_bearing / 2
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

class GaugeText:
    def __init__(self, x, y, w = None, h = 60, dummy_label = "00:00", caption = "", dummy_caption = None, italic = True, align_right = False, caption_left_of_data = False):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.dummy_label = dummy_label
        dummy_caption = dummy_caption if dummy_caption else caption

        self.padding = h / 8

        self.caption_text = Text(0,
                                 self.y + self.h - self.padding / 2,
                                 size = self.h * 0.5,
                                 dropshadow = self.h * 0.1 if globals['style']['text_shadows'] else 0,
                                 halign = Text.HALIGN_LEFT, valign = Text.VALIGN_BOTTOM_DESCENDERS)
        self.caption = caption

        self.label_text = Text(0,
                               self.y + self.h - self.padding / 2 if caption == "" else self.caption_text.y - self.caption_text.descender_y - self.caption_text.dropshadow,
                               size = self.h * 0.8,
                               dropshadow = self.h * 0.1 if globals['style']['text_shadows'] else 0,
                               face = Text.DEFAULT_MONO_FONT,
                               slant = cairo.FontSlant.ITALIC if italic else cairo.FontSlant.NORMAL,
                               halign = Text.HALIGN_RIGHT, valign = Text.VALIGN_BOTTOM_DESCENDERS if caption == "" else Text.VALIGN_BASELINE)
        
        if not align_right:
            if caption_left_of_data:
                self.caption_text.x = self.x + self.padding 
                self.label_text.x = self.caption_text.x + self.caption_text.measure(dummy_caption).width + self.caption_text.dropshadow + self.padding / 2 + self.label_text.measure(self.dummy_label).width
            else:
                self.label_text.x = self.x + self.padding + self.label_text.measure(self.dummy_label).width + self.label_text.dropshadow
                self.caption_text.x = self.label_text.x + self.padding / 2
        else:
            if caption_left_of_data:
                self.label_text.x = self.x + self.w - self.padding - self.label_text.dropshadow
                self.caption_text.x = self.label_text.x - self.label_text.measure(self.dummy_label).width - self.label_text.dropshadow - self.padding / 2 - self.caption_text.measure(dummy_caption).width - self.caption_text.dropshadow
            else:
                self.caption_text.x = self.x + self.w - self.padding - self.caption_text.measure(dummy_caption).width - self.caption_text.dropshadow
                self.label_text.x = self.caption_text.x - self.padding / 2
        
        if self.w is None:
            self.w = self.label_text.measure(self.dummy_label).width + self.padding * 2 + self.label_text.dropshadow
        
        self.bgpattern = make_background_pattern(0, self.y, 0, self.y + self.h)

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
        
        if val is not None:
            # render the big numbers
            self.label_text.color = (1.0, 1.0, 1.0)
            self.label_text.render(ctx, val)
        
            # render the little caption, if any
            self.caption_text.color = (1.0, 1.0, 1.0)
            self.caption_text.render(ctx, self.caption)

        ctx.pop_group_to_source()
        ctx.paint_with_alpha(0.9)
