#!/usr/bin/python

import math
import sys
import Queue
import threading
import numpy as np
import argparse

from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

from graph import *
from input import *
from overlay import *
from console import *

import ext

class Viewer:
	def __init__(self, window_name):
		glutCreateWindow(window_name)
		glutDisplayFunc(self.cb_display)
		glutMouseFunc(self.cb_mouse)
		glutMotionFunc(self.cb_motion)
		glutReshapeFunc(self.cb_reshape)
		glutKeyboardFunc(self.cb_keyboard)

		self.init()
		self.view = View()
		self.buttons_pressed = []

		self.layers = [self, self.view]

	def init(self):
		pass

	def cb_display(self):
		glClear(GL_COLOR_BUFFER_BIT)
		glClearColor(0, 0, 0, 1)
		glLoadIdentity()

		glPushMatrix()
		self.view.setup()

		for layer in self.layers:
			if hasattr(layer.__class__, 'draw_content'):
				layer.draw_content()

		glPopMatrix()

		for layer in self.layers:
			if hasattr(layer.__class__, 'draw_screen'):
				layer.draw_screen()

		glutSwapBuffers()

	def cb_mouse(self, button, state, x, y):
		if state == GLUT_DOWN:
			self.buttons_pressed.append(button)

		if state == GLUT_UP:
			self.buttons_pressed = [x for x in self.buttons_pressed if x != button]

		for layer in reversed(self.layers):
			if hasattr(layer.__class__, 'on_mouse_button'):
				if layer.on_mouse_button(button, state, x, self.screen_size[1] - y):
					break

		glutPostRedisplay()

	def cb_motion(self, x, y):
		if len(self.buttons_pressed) == 0:
			return

		for layer in reversed(self.layers):
			if hasattr(layer.__class__, 'on_drag'):
				if layer.on_drag(x, self.screen_size[1] - y):
					break

		glutPostRedisplay()

	def cb_reshape(self, w, h):
		glViewport(0, 0, w, h)
		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		gluOrtho2D(0.0, w, 0.0, h)
		glMatrixMode(GL_MODELVIEW)

		self.screen_size = (w, h)

		for layer in self.layers:
			if hasattr(layer.__class__, 'on_resize'):
				layer.on_resize(w, h)

	def cb_keyboard(self, key, x, y):
		for layer in reversed(self.layers):
			if hasattr(layer.__class__, 'on_key_press'):
				if layer.on_key_press(key):
					return

	def get_layer(self, type):
		a = [a for a in self.layers if a.__class__ == type]
		return a[0] if len(a) else None

class TemporalPlot(PlotLine):
	def __init__(self, viewer, x_offset, title=None):
		PlotLine.__init__(self, viewer.multitexture.get_height())
		self.viewer = viewer
		self.x_offset = x_offset
		self.title = title
		self.data[:] = np.zeros(self.points)

	def draw_screen(self):
		view = self.viewer.view

		glPushMatrix()
		glTranslated(self.x_offset, view.origin_y, 0)
		glScalef(-10.0, view.scale_y, 1.0)

		glColor4f(0.0, 0.0, 0.0, 0.7)
		glBegin(GL_QUADS)
		glVertex2f(-5.0, 0.0)
		glVertex2f(5.0, 0.0)
		glVertex2f(5.0, 1.0)
		glVertex2f(-5.0, 1.0)
		glEnd()
		glColor4f(1.0, 1.0, 1.0, 1.0)
		glRotatef(90, 0, 0, 1)
		PlotLine.draw_scroll(self, self.viewer.texture_edge)
		glPopMatrix()

		if self.title:
			self.viewer.overlay.draw_text_ss(self.x_offset - 45, view.origin_y + view.scale_y + 5,
												self.title)

	def set(self, row, value):
		self.data[row % self.points] = value

class TemporalFreqPlot(TemporalPlot):
	def __init__(self, viewer, title):
		TemporalPlot.__init__(self, viewer, 0, title)

	def draw_screen(self):
		glPushMatrix()
		self.viewer.view.setup()

		glColor4f(1.0, 1.0, 1.0, 1.0)
		glScalef(-1, 1, 1)
		glRotatef(90, 0, 0, 1)
		PlotLine.draw_scroll(self, self.viewer.texture_edge)

		glPopMatrix()

class DetectorScript():
	@staticmethod
	def peak(a, b, s):
		return (np.max(s[a:b]), np.argmax(s[a:b]) + a)

	@staticmethod
	def noise(a):
		return np.sort(a)[len(a)/4] * 2

	def cut(self, row):
		if self.event_marker.wip_mark == None:
			return

		(row_range, a, b) = self.event_marker.wip_mark
		self.event_marker.wip_mark = ((row_range[0], row), a, b)

	def plot(self, name, value):
		if not name in self.plots:
			self.plots[name] = TemporalPlot(self.viewer, self.plot_x_offset, name)
			self.plot_x_offset = self.plot_x_offset + 120

		self.plots[name].set(self.viewer.process_row, value)

	def plot_bin(self, name, value):
		if not name in self.plots:
			self.plots[name] = TemporalFreqPlot(self.viewer, name)

		self.plots[name].set(self.viewer.process_row, (float(value) / self.viewer.bins) * 2 - 1)

	def __init__(self, viewer, event_marker, file):
		self.viewer = viewer
		self.event_marker = event_marker
		self.plots = dict()
		self.plot_x_offset = 100

		self.__dict__['freq2bin'] = lambda x: int(x * viewer.bins / viewer.sig_input.sample_rate + viewer.bins / 2)
		self.__dict__['bin2freq'] = lambda x: float(x - viewer.bins / 2) / viewer.bins * viewer.sig_input.sample_rate
		self.__dict__['row_duration'] = float(viewer.bins - viewer.overlap) / viewer.sig_input.sample_rate

		self.__dict__['final'] = event_marker.final
		self.__dict__['event'] = event_marker.mark
		self.__dict__['cut'] = self.cut

		self.__dict__['plot'] = self.plot
		self.__dict__['plot_bin'] = self.plot_bin
		self.__dict__['plot_freq'] = lambda name, x: self.plot_bin(name, \
																	self.__dict__['freq2bin'](x))

		self.__dict__['noise'] = self.noise
		self.__dict__['peak'] = self.peak

		execfile(file, self.__dict__)

	def draw_screen(self):
		for plot in self.plots.values():
			plot.draw_screen()

	def on_lin_spectrum(self, spectrum):
		self.run(self.viewer.process_row, spectrum)

class EventMarker():
	def __init__(self, viewer):
		self.viewer = viewer
		self.marks = []
		self.wip_mark = None

	def mark(self, row_range, freq_range, description):
		self.wip_mark = (row_range, freq_range, description)

	def final(self):
		if self.wip_mark == None:
			return

		self.marks.append(self.wip_mark)
		self.wip_mark = None

	def draw_content(self):
		for (row_range, freq_range, description) in self.marks \
													+ ([self.wip_mark] if self.wip_mark else []):
			xa, xb = [self.viewer.bin_to_x(x) for x in freq_range]
			ya, yb = [self.viewer.row_to_y(x) for x in row_range]
			
			glLineWidth(2)
			glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
			glColor4f(0.0, 1.0, 0.0, 1.0)
			glBegin(GL_QUADS)
			glVertex2f(xa, ya)
			glVertex2f(xa, yb)
			glVertex2f(xb, yb)
			glVertex2f(xb, ya)
			glEnd()
			glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
			glLineWidth(1)

			glColor4f(1.0, 1.0, 1.0, 1.0)
			self.viewer.overlay.draw_text(xb, ya, description)

	def on_texture_insert(self):
		self.marks = [(a, b, c) for (a, b, c) in self.marks \
						if a[1] > self.viewer.texture_row - self.viewer.multitexture.get_height()]

class Texture():
	def __init__(self, image):
		self.texture = glGenTextures(1)

		glEnable(GL_TEXTURE_2D)

		glBindTexture(GL_TEXTURE_2D, self.texture)

		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);

		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, image.shape[1], image.shape[0], 0,
						GL_RGBA, GL_UNSIGNED_INT_8_8_8_8, image)

		glDisable(GL_TEXTURE_2D)

	def __del__(self):
		glDeleteTextures(self.texture)

	def draw(self):
		glEnable(GL_TEXTURE_2D)
		glBindTexture(GL_TEXTURE_2D, self.texture)
		glColor3f(1.0, 1.0, 1.0)

		glBegin(GL_QUADS)
		glTexCoord2i(0, 1)
		glVertex2i(0, 0)
		glTexCoord2i(1, 1)
		glVertex2i(1, 0)
		glTexCoord2i(1, 0)
		glVertex2i(1, 1)
		glTexCoord2i(0, 0)
		glVertex2i(0, 1)
		glEnd()

		glDisable(GL_TEXTURE_2D)

class RangeSelector():
	def __init__(self, viewer):
		self.texture = Texture(ext.mag2col((np.arange(64, dtype=np.float32) / 64) * 3.75 - 1.75).reshape((64, 1)))
		self.viewer = viewer
		self.histogram = PlotLine(90)
		self.hist_range = (-60, 20)
		self.dragging = None

	def mag_to_pixel(self, mag):
		return int((float(mag) - self.hist_range[0]) / (self.hist_range[1] - self.hist_range[0]) * 180)

	def pixel_to_mag(self, pixel):
		return float(pixel) / 180 * (self.hist_range[1] - self.hist_range[0]) + self.hist_range[0]

	def draw_screen(self):
		w, h = self.viewer.screen_size
		y_a, y_b = [self.mag_to_pixel(x) for x in self.viewer.mag_range]

		glPushMatrix()
		glTranslatef(w - 100, h - 200, 0)

		glColor4f(0.0, 0.0, 0.0, 0.7)

		glBegin(GL_QUADS)
		glVertex2i(0, 0)
		glVertex2i(80, 0)
		glVertex2i(80, 180)
		glVertex2i(0, 180)
		glEnd()

		glPushMatrix()
		glTranslatef(0, y_b, 0)
		glScalef(-10, y_a - y_b, 100)
		self.texture.draw()
		glPopMatrix()

		glPushMatrix()
		glTranslatef(5, 0, 0)
		glRotatef(90, 0, 0, 1)
		glScalef(180, -float(70) / self.viewer.bins, 1)
		glColor4f(1.0, 1.0, 1.0, 1.0)
		self.histogram.draw()
		glPopMatrix()

		glColor4f(1.0, 1.0, 1.0, 0.3)
		glBegin(GL_QUADS)
		glVertex2i(0, y_a - 10)
		glVertex2i(0, y_a)
		glVertex2i(80, y_a)
		glVertex2i(80, y_a - 10)

		glVertex2i(0, y_b + 10)
		glVertex2i(0, y_b)
		glVertex2i(80, y_b)
		glVertex2i(80, y_b + 10)

		glEnd()

		glPopMatrix()

	def on_log_spectrum(self, spectrum):
		(self.histogram.data[:], _) = np.histogram(spectrum, bins=90, range=self.hist_range)

	def on_mouse_button(self, button, state, x, y):
		if button != GLUT_LEFT_BUTTON:
			return False

		if state == GLUT_DOWN:
			w, h = self.viewer.screen_size
			mag_a, mag_b = self.viewer.mag_range
			pix_a, pix_b = [self.mag_to_pixel(l) for l in (mag_a, mag_b)]

			if w - 100 <= x <= w - 20:
				if y + 10 >= h - 200 + pix_a >= y:
					self.dragging = (pix_a - y, None)
					return True

				if y - 10 <= h - 200 + pix_b <= y:
					self.dragging = (None, pix_b - y)
					return True

			if w - 110 <= x <= w - 100 and pix_a <= y - h + 200 <= pix_b:
				self.dragging = (pix_a - y, pix_b - y)
				return True

			return False

		if state == GLUT_UP:
			if self.dragging != None:
				self.dragging = None
				return True
			else:
				return False

	def on_drag(self, x, y):
		if self.dragging != None:
			self.viewer.mag_range = tuple(self.pixel_to_mag(d + y) if d != None else x for (x, d) \
											in zip(self.viewer.mag_range, self.dragging))
			return True
		else:
			return False

class WaterfallWindow(Viewer):
	def __init__(self, sig_input, bins, overlap = 0):
		if bins % 1024 != 0:
			raise NotImplementedError("number of bins must be a multiple of 1024")

		Viewer.__init__(self, "PySDR")
		glutIdleFunc(self.cb_idle)
		self.init()

		self.mag_range = (-45, 5)
		self.calibrate_rq = False

		self.sig_input = sig_input
		self.bins = bins
		self.window = 0.5 * (1.0 - np.cos((2 * math.pi * np.arange(self.bins)) / self.bins))
		self.overlap = overlap

		self.multitexture = MultiTexture(1024, 1024, self.bins / 1024, 1)

		self.overlay = PlotOverlay(self, self.sig_input)
		event_marker = EventMarker(self)
		detector_script = DetectorScript(self, event_marker, "detector.py")
		self.layers = self.layers + [event_marker, detector_script,
										self.overlay, RangeSelector(self),
										Console(self, globals())]

		self.texture_inserts = Queue.Queue()
		self.texture_edge = 0

		self.texture_row = 0
		self.process_row = 0

		self.process_t = threading.Thread(target=self.process)
		self.process_t.setDaemon(True)
		self.process_t.start()

	def start(self):
		self.sig_input.start()

	def init(self):
		glLineWidth(1.0)
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

	def draw_content(self):
		glPushMatrix()
		glTranslated(-1.0, 0.0, 0.0)
		glScalef(2.0, 1.0, 1.0)
		self.multitexture.draw_scroll(self.texture_edge)
		glPopMatrix()

	def bin_to_x(self, bin):
		return float(bin) / self.bins * 2 - 1

	def row_to_y(self, row):
		return float(row - self.texture_row) / self.multitexture.get_height() + 1.0

	def cb_idle(self):
		try:
			while True:
				rec = self.texture_inserts.get(block=True, timeout=0.01)
				self.multitexture.insert(self.texture_edge, rec)
				self.texture_row = self.texture_row + 1
				self.texture_edge = self.texture_row % self.multitexture.get_height()

				for layer in self.layers:
					if hasattr(layer.__class__, 'on_texture_insert'):
						layer.on_texture_insert()

				glutPostRedisplay()
		except Queue.Empty:
			return

	def on_key_press(self, key):
		if key == 'c':
			self.calibrate_rq = True
			return True

		if key == 'm':
			self.view.set_scale(self.multitexture.get_width(), self.multitexture.get_height(),
								self.screen_size[0] / 2, self.screen_size[1] / 2)
			glutPostRedisplay()

	def process(self):
		signal = np.zeros(self.bins, dtype=np.complex64)

		while True:
			signal[0:self.overlap] = signal[self.bins - self.overlap:self.bins]
			signal[self.overlap:self.bins] = self.sig_input.read(self.bins - self.overlap)

			spectrum = np.absolute(np.fft.fft(np.multiply(signal, self.window)))
			spectrum = np.concatenate((spectrum[self.bins/2:self.bins], spectrum[0:self.bins/2]))

			for layer in reversed(self.layers):
				if hasattr(layer.__class__, 'on_lin_spectrum'):
					layer.on_lin_spectrum(spectrum)

			spectrum = np.log10(spectrum) * 10

			for layer in reversed(self.layers):
				if hasattr(layer.__class__, 'on_log_spectrum'):
					layer.on_log_spectrum(spectrum)

			if self.calibrate_rq:
				self.calibrate_rq = False

				a = int(((-self.view.origin_x) / self.view.scale_x + 1)
						/ 2 * self.bins)
				b = int(((-self.view.origin_x + self.screen_size[0]) / self.view.scale_x + 1)
						/ 2 * self.bins)

				a = max(0, min(self.bins - 1, a))
				b = max(0, min(self.bins - 1, b))

				if a != b:
					area = spectrum[a:b]
					mag_range = (np.min(area) + 0.5, np.max(area) + 1.0)

					if [math.isnan(a) or math.isinf(a) for a in mag_range] == [False, False]:
						self.mag_range = mag_range

			try:
				scale = 3.75 / (self.mag_range[1] - self.mag_range[0])
			except ZeroDivisionError:
				scale = 3.75 / 0.00001

			shift = -self.mag_range[0] * scale - 1.75

			line = ext.mag2col((spectrum * scale + shift).astype('f'))
			self.process_row = self.process_row + 1
			self.texture_inserts.put(line)

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Plot live spectral waterfall of an IQ signal.')
	parser.add_argument('-b', '--bins', type=int, default=4096,
						help='number of bins (default: %(default)s)')
	parser.add_argument('-j', '--jack', metavar='NAME', default='pysdr',
						help='feed signal from JACK under the given name')
	parser.add_argument('-r', '--raw', metavar='RATE', type=int,
						help='feed signal from the standard input, 2 channel \
								interleaved floats with the given samplerate')
	parser.add_argument('-o', '--overlap', type=float, default=0.75,
						help='overlap between consecutive windows as a proportion \
								of the number of bins (default: %(default)s)')

	args = parser.parse_args()

	overlap_bins = int(args.bins * args.overlap)

	if not (overlap_bins >= 0 and overlap_bins < args.bins):
		raise ValueError("number of overlapping bins is out of bounds")

	if args.raw:
		sig_input = RawSigInput(args.raw, 2, np.dtype(np.float32), sys.stdin)
	else:
		sig_input = JackInput(args.jack)

	glutInit()
	glutInitWindowSize(640, 480)
	glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA)

	viewer = WaterfallWindow(sig_input, args.bins, overlap=overlap_bins)
	viewer.start()

	glutMainLoop()
