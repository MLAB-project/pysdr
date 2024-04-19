import math

from .input import *

from OpenGL.GL import *
from OpenGL.GLUT import *

class View:
    def __init__(self):
        self.scale_x = 640.0
        self.scale_y = 480.0
        self.origin_x = 0.0
        self.origin_y = 0.0
        self.screen_offset = (0, 0)

    def on_mouse_button(self, button, state, x, y):
        if state != GLUT_DOWN:
            return

        self.button_right = button == GLUT_RIGHT_BUTTON
        self.start_x = x
        self.start_y = y
        self.drag_x = x
        self.drag_y = y

    def set_scale(self, sx, sy, px, py):
        sx, sy = float(sx), float(sy)
        self.origin_x = (self.origin_x - px) * (sx / self.scale_x) + px
        self.origin_y = (self.origin_y - py) * (sy / self.scale_y) + py
        self.scale_x = sx
        self.scale_y = sy

    def on_drag(self, x, y):
        if self.button_right:
            self.set_scale(self.scale_x * math.pow(1.01, x - self.drag_x),
                            self.scale_y * math.pow(1.01, y - self.drag_y),
                            self.start_x, self.start_y)
        else:
            self.origin_x += x - self.drag_x
            self.origin_y += y - self.drag_y
        self.drag_x = x
        self.drag_y = y

    def from_screen(self, x, y):
        return ((x - self.origin_x) / self.scale_x, (y - self.origin_y) / self.scale_y)

    def to_screen(self, x, y):
        return (x * self.scale_x + self.origin_x, y * self.scale_y + self.origin_y)

    def setup(self):
        glTranslated(self.origin_x, self.origin_y, 0)
        glScaled(self.scale_x, self.scale_y, 1.0)

UNIT_HZ = ((1e6, "MHz"), (1e3, "kHz"), (1e0, "Hz"))
UNIT_SEC = ((60, "min"), (1, "sec"))
UNIT_ONE = ((1.0, ""),)

def _unit_format(unit, base):
    if unit is None:
        return lambda x: ""

    for unit_base, postfix in unit:
        if unit_base < base * 10 or unit_base == 1:
            fmt_str = "%%.%df %s" % (max(0, math.ceil(math.log10(unit_base / base))), postfix)
            return lambda x: fmt_str % (x / unit_base,)

def _axis(a, b, scale, offset, unit, cutoff):
    visible_area = abs((b - a) * scale)

    base = math.log(visible_area, 10)
    for x in [math.log10(5), math.log10(2), 0]:
        if math.floor(base) - x >= base - (1 + 1e-5):
            base = math.floor(base) - x
            break

    base = 10 ** base * (scale / abs(scale))

    ticks = [((m * base - offset) / scale, m * base) for m
             in range(int(math.floor((a * scale + offset) / base)),
                      int(math.ceil((b * scale + offset) / base) + 1))]
    ticks = [m for m in ticks if m[0] >= cutoff[0] + -1e-5 and m[0] <= cutoff[1] + 1e-5]

    fmt = _unit_format(unit, abs(base))
    return [(m[0], fmt(m[1] + 0.0)) for m in ticks]

def static_axis(unit, scale, cutoff=(0.0, 1.0), offset=0.0):
    return lambda a, b: _axis(a, b, scale, offset, unit, cutoff)

def hms_base(a):
    for s in [1, 60]:
        for x in [1, 2, 3, 5, 10, 20, 30, 60]:
            if a / (s * x) < 10:
                return x * s

    return 3600 * 60

def time_of_day_axis(a, b, scale, offset, unit, cutoff):
    visible_area = abs((b - a) * scale)

    if visible_area < 10:
        base = math.log(visible_area, 10)

        for x in [math.log10(5), math.log10(2), 0]:
            if math.floor(base) - x >= base - (1 + 1e-5):
                base = math.floor(base) - x
                break

        base = 10 ** base * (scale / abs(scale))
    else:
        base = float(hms_base(visible_area))

    ticks = [((m * base - offset) / scale, m * base) for m
             in range(int(math.floor((a * scale + offset) / base)),
                      int(math.ceil((b * scale + offset) / base) + 1))]
    ticks = [m for m in ticks if m[0] >= cutoff[0] + -1e-5 and m[0] <= cutoff[1] + 1e-5]

    digits = max(0, math.ceil(-math.log10(base)))

    fmt_str = "%%02d:%%02d:%%02.%df" % digits
    fmt = lambda a: fmt_str % ((a / 3600) % 24, (a / 60) % 60, a % 60)

    return [(m[0], fmt(m[1])) for m in ticks]

class PlotAxes:
    def __init__(self, viewer, axis_x, axis_y):
        self.viewer = viewer
        self.tickers = (axis_x, axis_y)

    def draw_text_ss(self, x, y, text):
        x, y = self.viewer.view.screen_offset[0] + x, self.viewer.view.screen_offset[1] + y
        glWindowPos2i(int(x), int(y))
        for c in text:
            glutBitmapCharacter(GLUT_BITMAP_8_BY_13, ord(c))

    def draw_text(self, x, y, text):
        glPushMatrix()
        glLoadIdentity()

        (sx, sy) = self.viewer.view.to_screen(x, y)
        self.draw_text_ss(sx + 5, sy + 5, text)

        glPopMatrix()

    def draw_content(self):
        view = self.viewer.view

        a, b = view.from_screen(0, 0), view.from_screen(*self.viewer.screen_size)

        for axis, ticker, m in zip((0, 1), self.tickers,
                                   (lambda a, b: (a, b), lambda a, b: (b, a))):
            if ticker == None:
                continue

            (aa, oa), (ab, ob) = m(*a), m(*b)
            ticks = ticker(aa, ab)

            glColor4f(1.0, 1.0, 1.0, 0.25)
            glBegin(GL_LINES)
            for pos, label in ticks:
                    glVertex2f(*m(pos, oa))
                    glVertex2f(*m(pos, ob))
            glEnd()

            glColor4f(1.0, 1.0, 1.0, 1.0)
            for pos, label in ticks:
                x, y = m(view.to_screen(pos, pos)[axis] + 5, 5)
                self.draw_text_ss(x, y, label)
