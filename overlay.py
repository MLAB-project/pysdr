import math

from input import *

from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

class View:
	def __init__(self):
		self.scale_x = 640.0
		self.scale_y = 480.0
		self.origin_x = 0.0
		self.origin_y = 0.0

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
		glScalef(self.scale_x, self.scale_y, 1.0)

class PlotOverlay:
	def __init__(self, viewer, sig_input):
		self.viewer = viewer
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
			if l <= b[0] + 1 or b[0] == 0:
				return ("%%.%df %%s" % max(0, l - b[0])) % (x * math.pow(10, b[0]), b[1])

	def draw_text_ss(self, x, y, text):
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

		x_a = -view.origin_x / view.scale_x
		x_b = x_a + self.viewer.screen_size[0] / view.scale_x

		y_a = -view.origin_y / view.scale_y
		y_b = y_a + self.viewer.screen_size[1] / view.scale_y

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
			self.draw_text_ss(((x/bw - x_a) / (x_b - x_a)) * self.viewer.screen_size[0] + 5, 5,
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
