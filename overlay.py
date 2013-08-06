import math

from input import *

from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

import glFreeType

class View:
	def __init__(self):
		self.scale_x = 640.0
		self.scale_y = 480.0
		self.origin_x = 0.0
		self.origin_y = 0.0

	def click(self, right_click, x, y):
		self.right_click = right_click
		self.start_x = x
		self.start_y = y
		self.drag_x = x
		self.drag_y = y

	def set_dimensions(self, w, h):
		self.width = w
		self.height = h

	def get_height(self):
		return self.height

	def get_width(self):
		return self.width

	def drag(self, x, y):
		if self.right_click:
			x_c = math.pow(1.01, x - self.drag_x)
			y_c = math.pow(1.01, y - self.drag_y)
			self.origin_x = (self.origin_x - self.start_x) * x_c + self.start_x
			self.origin_y = (self.origin_y - self.start_y) * y_c + self.start_y
			self.scale_x *= x_c
			self.scale_y *= y_c
		else:
			self.origin_x += x - self.drag_x
			self.origin_y += y - self.drag_y
		self.drag_x = x
		self.drag_y = y

	def setup(self):
		glTranslated(self.origin_x, self.origin_y, 0)
		glScalef(self.scale_x, self.scale_y, 1.0)


class PlotOverlay:
	def __init__(self, view, sig_input):
		self.font = glFreeType.font_data("font.ttf", 10)
		self.view = view
		self.sig_input = sig_input

	@staticmethod
	def get_base(a, b):
		p = math.log(b - a, 0.1)
		c = math.ceil(p)

		if c + math.log(0.2, 0.1) < p + 1:
			c += math.log(0.2, 0.1)

		if c + math.log(0.5, 0.1) < p + 1:
			c += math.log(0.5, 0.1)

		return math.pow(0.1, c)

	@staticmethod
	def get_marks(a, b, s):
		return [m * s for m in range(int(math.ceil(a / s)) - 1,
									int(math.ceil(b / s)) + 2)]

	@staticmethod
	def format_freq(x, base):
		l = int(math.ceil(math.log(base, 0.1)))

		for b in [(-6, "MHz"), (-3, "kHz"), (0, "Hz")]:
			if l <= b[0] + 1:
				return ("%%.%df %%s" % max(0, l - b[0])) % (x * math.pow(10, b[0]), b[1])

	def draw(self):
		x_a = -self.view.origin_x / self.view.scale_x
		x_b = x_a + self.view.get_width() / self.view.scale_x

		y_a = -self.view.origin_y / self.view.scale_y
		y_b = y_a + self.view.get_height() / self.view.scale_y

		bw = self.sig_input.sample_rate / 2

		base = self.get_base(x_a * bw, x_b * bw)
		marks = [l for l in self.get_marks(x_a * bw, x_b * bw, base) if (l/bw >= -1.0001 and l/bw <= 1.0001)]

		glColor4f(1.0, 1.0, 1.0, 0.25)
		glBegin(GL_LINES)

		for x in marks:
			glVertex2f(x / bw, y_a)
			glVertex2f(x / bw, y_b)

		glEnd()

		glColor4f(1.0, 1.0, 1.0, 1.0)
		
		glPushMatrix()
		glLoadIdentity()

		for x in marks:
			self.font.glPrint(((x/bw - x_a) / (x_b - x_a)) * self.view.get_width() + 5, 5,
				self.format_freq(x, base))

		glPopMatrix()

		base = self.get_base(y_a, y_b)
		marks = [l for l in self.get_marks(y_a, y_b, base) if l >= 0 and l <= 1]

		glColor4f(1.0, 1.0, 1.0, 0.25)
		glBegin(GL_LINES)

		for y in marks:
			glVertex2f(x_a, y)
			glVertex2f(x_b, y)

		glEnd()
