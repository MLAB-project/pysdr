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

sys.path.append("./pysdrext/pysdrext_directory")
import pysdrext

class Detector():
	@staticmethod
	def peak(a, b, s):
		return (np.max(s[a:b]), np.argmax(s[a:b]) + a)

	@staticmethod
	def noise(a):
		return np.sort(a)[len(a)/4] + np.log(2)

	def __init__(self, file, wf_win):
		self.__dict__['mark'] = wf_win.add_mark
		self.__dict__['noise'] = self.noise
		self.__dict__['peak'] = self.peak
		self.__dict__['freq2bin'] = lambda x: int(x * wf_win.bins / wf_win.sig_input.sample_rate + wf_win.bins / 2)
		execfile(file, self.__dict__)

class WaterfallWindow():
	def __init__(self, sig_input, bins, overlap = 0):
		if bins % 1024 != 0:
			raise NotImplementedError("number of bins must be a multiple of 1024")

		self.mag_a = -5
		self.mag_b = 5
		self.calibrate_rq = False

		self.sig_input = sig_input
		self.bins = bins
		self.window = 0.5 * (1.0 - np.cos((2 * math.pi * np.arange(self.bins)) / self.bins))
		self.overlap = overlap

		glutCreateWindow('PySDR')
		glutDisplayFunc(self.display)
		glutIdleFunc(self.idle)
		glutMouseFunc(self.mouse)
		glutMotionFunc(self.motion)
		glutReshapeFunc(self.reshape)
		glutKeyboardFunc(self.keyboard)

		self.init()

		self.view = View()
		self.multitexture = MultiTexture(1024, 1024, self.bins / 1024, 1)
		self.overlay = PlotOverlay(self.view, self.sig_input)

		self.button_down = False
		self.console_active = False

		self.wf_inserts = Queue.Queue()
		self.wf_rows_sum = 0
		self.wf_edge = 0

		self.process_t = threading.Thread(target=self.process)
		self.process_t.setDaemon(True)
		self.process_t.start()

		self.detectors = []
		self.marks = []

	def start(self):
		self.sig_input.start()

	def init(self):
		glLineWidth(1.0)
		glEnable(GL_BLEND)

	def display(self):
		glClear(GL_COLOR_BUFFER_BIT)

		glLoadIdentity()

		glPushMatrix()

		self.view.setup()

		glPushMatrix()
		glTranslated(-1.0, 0.0, 0.0)
		glScalef(2.0, 1.0, 1.0)
		self.multitexture.draw_scroll(self.wf_edge)
		glPopMatrix()

		self.overlay.draw()

		glColor3f(1.0, 1.0, 1.0)

		row_size = 1.0 / self.multitexture.get_height()
		for mark in self.marks:
			self.overlay.draw_text(mark[0], 1.0 + row_size * (mark[1] - self.wf_rows_sum), mark[2])

		glPopMatrix()

		glutSwapBuffers()

	def add_mark(self, row, bin, text):
		self.marks.append((float(bin) / self.bins * 2 - 1,
							row, text))

	def clean_marks(self):
		pitfall = self.wf_rows_sum - self.multitexture.get_height()
		self.marks = [x for x in self.marks if not x[1] < pitfall]

	def mouse(self, button, state, x, y):
		if state == GLUT_DOWN:
			self.button_down = True
			self.view.click(button == GLUT_RIGHT_BUTTON, x, self.view.get_height() - y)

		if state == GLUT_UP:
			self.button_down = False
		glutPostRedisplay()

	def motion(self, x, y):
		if self.button_down:
			self.view.drag(x, self.view.get_height() - y)
		glutPostRedisplay()

	def reshape(self, w, h):
		glViewport(0, 0, w, h)
		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		gluOrtho2D(0.0, w, 0.0, h)
		glMatrixMode(GL_MODELVIEW)

		self.view.set_dimensions(w, h)

	def keyboard(self, key, x, y):
		if key == 'c':
			self.calibrate_rq = True

		if key == 'm':
			self.view.set_scale(self.multitexture.get_width(), self.multitexture.get_height(),
								self.view.width / 2, self.view.height / 2)
			glutPostRedisplay()

	def idle(self):
		try:
			while True:
				rec = self.wf_inserts.get(block = True, timeout = 0.02)
				self.multitexture.insert(self.wf_edge, rec)

				self.wf_rows_sum += 1
				self.wf_edge = self.wf_rows_sum % self.multitexture.get_height()
				self.clean_marks()

				glutPostRedisplay()
		except Queue.Empty:
			return

	def process(self):
		signal = np.zeros(self.bins, dtype=np.complex64)
		iteration = 0

		while True:
			signal[0:self.overlap] = signal[self.bins - self.overlap:self.bins]
			signal[self.overlap:self.bins] = self.sig_input.read(self.bins - self.overlap)
			spectrum = np.log(np.absolute(np.fft.fft(np.multiply(signal, self.window))))
			spectrum = np.concatenate((spectrum[self.bins/2:self.bins],
										spectrum[0:self.bins/2]))

			for detector in self.detectors:
				try:
					detector.run(iteration, spectrum)
				except Exception as e:
					print e

			if self.calibrate_rq:
				self.calibrate_rq = False

				a = int(((-self.view.origin_x) / self.view.scale_x + 1)
						/ 2 * self.bins)
				b = int(((-self.view.origin_x + self.view.width) / self.view.scale_x + 1)
						/ 2 * self.bins)

				a = max(0, min(self.bins - 1, a))
				b = max(0, min(self.bins - 1, b))

				if a != b:
					area = spectrum[a:b]
					self.mag_a = np.min(area) - 0.5
					self.mag_b = np.max(area) + 1.0

			scale = 2.75 / (self.mag_b - self.mag_a)
			shift = -self.mag_a * scale - 1.75

			line = pysdrext.mag2col((spectrum * scale + shift).astype('f'))
			iteration = iteration + 1
			self.wf_inserts.put(line)

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

	waterfall_win = WaterfallWindow(sig_input, args.bins, overlap=overlap_bins)
	waterfall_win.detectors = [Detector("detector.py", waterfall_win)]
	waterfall_win.start()

	glutMainLoop()
