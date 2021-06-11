import cairo
from .utils import *

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
