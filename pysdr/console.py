import sys

from code import InteractiveConsole

from OpenGL.GL import *
from OpenGL.GLUT import glutBitmapCharacter, GLUT_BITMAP_8_BY_13

class Console(InteractiveConsole):
    """Quake-like console"""

    CHAR_WIDTH = 8
    CHAR_HEIGHT = 13

    @staticmethod
    def draw_string(x, y, string):
        return
        glWindowPos2i(x, y)
        for c in string:
            glutBitmapCharacter(GLUT_BITMAP_8_BY_13, ord(c))

    @staticmethod
    def draw_cursor(x, y, w, h):
        glColor4f(1.0, 1.0, 1.0, 1.0)

        glBegin(GL_QUADS)
        glVertex2i(x, y)
        glVertex2i(x + w, y)
        glVertex2i(x + w, y + h)
        glVertex2i(x, y + h)
        glEnd()

    def __init__(self, viewer, locals):
        self.viewer = viewer
        self.lines = []
        self.prompt = ">>> "
        self.last_line = ""
        self.stdout = self.stderr = self
        self.active = False
        InteractiveConsole.__init__(self, locals=locals)

        self.on_resize(*getattr(viewer, 'screen_size', (1024, 1024)))

        self.prev_stdout = sys.stdout
        sys.stdout = self

    def on_resize(self, w, h):
        self.lines_cutoff = max((h - 20) / self.CHAR_HEIGHT, 1)
        self.columns_cutoff = max((w - 20) / self.CHAR_WIDTH, 1)

    def draw_screen(self):
        if not self.active:
            return

        glColor4f(0.0, 0.0, 0.0, 0.75)

        w, h = self.viewer.screen_size

        glBegin(GL_QUADS)
        glVertex2i(0, 0)
        glVertex2i(0, h)
        glVertex2i(w, h)
        glVertex2i(w, 0)
        glEnd()

        glColor4f(1.0, 1.0, 1.0, 1.0)

        y = 10 + self.CHAR_HEIGHT
        for line in reversed(self.lines):
            self.draw_string(10, y, line)
            y += self.CHAR_HEIGHT

        self.draw_string(10, 10, self.prompt + self.last_line)
        self.draw_cursor(10 + len(self.prompt + self.last_line) * self.CHAR_WIDTH,
                            8, self.CHAR_WIDTH, self.CHAR_HEIGHT)

    def write(self, msg):
        self.prev_stdout.write(msg)

        split = msg.split("\n")

        if len(self.lines) > 0:
            split[0] = self.lines.pop() + split[0]

        self.lines += [s[x:x + self.columns_cutoff] for s in split for x \
                        in (range(0, len(s), self.columns_cutoff) if len(s) else [0])]

        while len(self.lines) > self.lines_cutoff:
            self.lines.pop(0)

    def on_key_press(self, key):
        if key == '`':
            self.active = not self.active
            return True

        if not self.active:
            return False

        if key == '\r':
            print self.prompt + self.last_line
            if self.push(self.last_line):
                self.prompt = "... "
            else:
                self.prompt = ">>> "
            self.last_line = " " * (len(self.last_line) - len(self.last_line.lstrip()))
        else:
            if key == '\b':
                if len(self.last_line.lstrip()) == 0:
                    self.last_line = self.last_line[:len(self.last_line) - ((len(self.last_line) - 1) % 4 + 1)]
                else:
                    self.last_line = self.last_line[:-1]
            elif key == '\t':
                self.last_line += " " * (4 - (len(self.last_line) % 4))
            else:
                self.last_line += key

        return True
