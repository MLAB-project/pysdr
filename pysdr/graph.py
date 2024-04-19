import math
import numpy as np

from OpenGL.GL import *

class PlotLine:
    def __init__(self, points):
        self.points = points
        self.array = np.zeros((self.points, 2), 'f')
        self.data = self.array[:,1]
        self.array[:,0] = np.arange(self.points, dtype=np.float) / self.points

    def draw(self):
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(2, GL_FLOAT, 0, self.array)
        glDrawArrays(GL_LINE_STRIP, 0, self.points)
        glDisableClientState(GL_VERTEX_ARRAY)

    def draw_section(self, start, end):
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(2, GL_FLOAT, 0, self.array)

        glPushMatrix()

        pos = start
        while pos < end:
            offset = pos % self.points

            if offset == self.points - 1:
                glBegin(GL_LINES)
                glVertex2f(0.0, self.data[-1])
                glVertex2f(1.0 / self.points, self.data[0])
                glEnd()
                glTranslatef(1.0 / self.points, 0, 0)
                pos += 1
                continue

            advance = min(self.points - offset - 1, end - pos)

            glPushMatrix()
            glTranslatef(-float(offset) / self.points, 0, 0)
            glDrawArrays(GL_LINE_STRIP, offset, advance + 1)
            glPopMatrix()

            glTranslatef(float(advance) / self.points, 0, 0)
            pos += advance

        glPopMatrix()

        glDisableClientState(GL_VERTEX_ARRAY)

class MultiTexture():
    """Abstracting grid of textures"""
    def __init__(self, unit_width, unit_height, units_x, units_y,
                 format=GL_RGB, type=GL_BYTE):
        self.unit_width = unit_width
        self.unit_height = unit_height

        self.units_x = units_x
        self.units_y = units_y

        self.textures = glGenTextures(units_x * units_y)

        self.format = format
        self.type = type

        if not isinstance(self.textures, np.ndarray):
            self.textures = [self.textures]

        init_image = np.zeros(self.unit_width * self.unit_height * 16, dtype=np.uint8)

        for i in range(units_x * units_y):
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.textures[i])
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexImage2D(GL_TEXTURE_2D, 0, format, self.unit_width,
                         self.unit_height, 0, format, type, init_image)

    def get_width(self):
        return self.units_x * self.unit_width

    def get_height(self):
        return self.units_y * self.unit_height

    def __del__(self):
        glDeleteTextures(self.textures)

    def insert(self, y, line, format=GL_RGBA, type=GL_UNSIGNED_INT_8_8_8_8):
        if y > self.units_y * self.unit_height:
            raise Error("out of bounds")

        base = math.trunc(y / self.unit_height) * self.units_x
        offset_y = y - math.trunc(y / self.unit_height) * self.unit_height

        for x in range(self.units_x):
            glBindTexture(GL_TEXTURE_2D, self.textures[base + x])
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, offset_y, self.unit_width, 1, format, type,
                            line[x * self.unit_width:(x + 1) * self.unit_width])

    def draw(self):
        glEnable(GL_TEXTURE_2D)
        glColor3f(1.0, 1.0, 1.0)

        for y in range(self.units_y):
            for x in range(self.units_x):
                glBindTexture(GL_TEXTURE_2D, self.textures[self.units_x * y + x])
                xa, xb = (float(x) / self.units_x), (float(x + 1) / self.units_x)
                ya, yb = (float(y) / self.units_y), (float(y + 1) / self.units_y)

                glBegin(GL_QUADS)
                glTexCoord2f(0, 0)
                glVertex2f(xa, ya)
                glTexCoord2f(0, 1)
                glVertex2f(xa, yb)
                glTexCoord2f(1, 1)
                glVertex2f(xb, yb)
                glTexCoord2f(1, 0)
                glVertex2f(xb, ya)
                glEnd()

        glDisable(GL_TEXTURE_2D)

    def draw_row(self, edge, row):
        y = row - (edge / self.unit_height)

        if y < 0:
            y = y + self.units_y

        row_shift = float(edge % self.unit_height) / (self.units_y * self.unit_height)

        if y == 0:
            ya, yb = 1.0 - row_shift, 1.0
            tya, tyb = 0, row_shift * self.units_y
            for x in range(self.units_x):
                glBindTexture(GL_TEXTURE_2D, self.textures[self.units_x * row + x])
                xa, xb = (float(x) / self.units_x), (float(x + 1) / self.units_x)

                glBegin(GL_QUADS)
                glTexCoord2f(0, tya)
                glVertex2f(xa, ya)
                glTexCoord2f(0, tyb)
                glVertex2f(xa, yb)
                glTexCoord2f(1, tyb)
                glVertex2f(xb, yb)
                glTexCoord2f(1, tya)
                glVertex2f(xb, ya)
                glEnd()

            ya, yb = 0.0, (1.0 / float(self.units_y)) - row_shift
            tya, tyb = row_shift * self.units_y, 1.0
            for x in range(self.units_x):
                glBindTexture(GL_TEXTURE_2D, self.textures[self.units_x * row + x])
                xa, xb = (float(x) / self.units_x), (float(x + 1) / self.units_x)

                glBegin(GL_QUADS)
                glTexCoord2f(0, tya)
                glVertex2f(xa, ya)
                glTexCoord2f(0, tyb)
                glVertex2f(xa, yb)
                glTexCoord2f(1, tyb)
                glVertex2f(xb, yb)
                glTexCoord2f(1, tya)
                glVertex2f(xb, ya)
                glEnd()

        else:
            ya, yb = (float(y) / self.units_y) - row_shift, (float(y + 1) / self.units_y) - row_shift

            for x in range(self.units_x):
                glBindTexture(GL_TEXTURE_2D, self.textures[self.units_x * row + x])
                xa, xb = (float(x) / self.units_x), (float(x + 1) / self.units_x)

                glBegin(GL_QUADS)
                glTexCoord2f(0, 0)
                glVertex2f(xa, ya)
                glTexCoord2f(0, 1)
                glVertex2f(xa, yb)
                glTexCoord2f(1, 1)
                glVertex2f(xb, yb)
                glTexCoord2f(1, 0)
                glVertex2f(xb, ya)
                glEnd()


    def draw_scroll(self, edge):
        glEnable(GL_TEXTURE_2D)
        glColor3f(1.0, 1.0, 1.0)

        for y in range(self.units_y):
            self.draw_row(edge, y)

        glDisable(GL_TEXTURE_2D)

class WaterfallFlat():
    """Simple waterfall implementation"""
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.top_y = 0
        self.texture = glGenTextures(1)

        glEnable(GL_TEXTURE_2D)

        glBindTexture(GL_TEXTURE_2D, self.texture)

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);

        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.width, self.height, 0, GL_RGB, GL_BYTE, 0)

    def __del__(self):
        if hasattr(self, 'textures') and self.textures is not None:
            glDeleteTextures(self.textures)

    def insert(self, line):
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, self.top_y, self.width, 1,
                        GL_RGBA, GL_UNSIGNED_INT_8_8_8_8, line)

        self.top_y += 1

        if self.top_y >= self.height:
            self.top_y = 0

    def draw(self):
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glColor3f(1.0, 1.0, 1.0)

        glBegin(GL_QUADS)

        if self.top_y != 0:
            glTexCoord2f(0, float(self.top_y) / self.height)
            glVertex2f(0, 0)
            glTexCoord2f(1.0, float(self.top_y) / self.height)
            glVertex2f(1.0, 0)
            glTexCoord2f(1.0, 0)
            glVertex2f(1.0, float(self.top_y) / self.height)
            glTexCoord2f(0, 0)
            glVertex2f(0, float(self.top_y) / self.height)

        if self.top_y != self.height - 1:
            glTexCoord2f(0.0, 1.0)
            glVertex2f(0, float(self.top_y) / self.height)
            glTexCoord2f(1.0, 1.0)
            glVertex2f(1.0, float(self.top_y) / self.height)
            glTexCoord2f(1.0, float(self.top_y) / self.height)
            glVertex2f(1.0, 1.0)
            glTexCoord2f(0.0, float(self.top_y) / self.height)
            glVertex2f(0, 1.0)

        glEnd()

        glDisable(GL_TEXTURE_2D)
