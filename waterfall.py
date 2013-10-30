import math
import sys
import subprocess
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

mag_a = -5
mag_b = 5

view = View()
overlay = None

def initFun():
	glClearColor(0.0, 0.0, 0.0, 0.0)
	glColor3f(0.0, 0.0, 0.0)
	glLineWidth(1.0)
	glEnable(GL_BLEND)

def displayFun():
	glClear(GL_COLOR_BUFFER_BIT)

	glLoadIdentity()

	glPushMatrix()

	view.setup()

	glPushMatrix()
	glTranslated(-1.0, 0.0, 0.0)
	glScalef(2.0, 1.0, 1.0)
	multitexture.draw_scroll(wf_edge)
	glPopMatrix()
	
	overlay.draw()

	glPopMatrix()

	glutSwapBuffers()
	glutPostRedisplay()

button_down = False

def mouseFun(button, state, x, y):
	global button_down
	if state == GLUT_DOWN:
		button_down = True
		view.click(button == GLUT_RIGHT_BUTTON, x, view.get_height() - y)

	if state == GLUT_UP:
		button_down = False
	glutPostRedisplay()

def motionFun(x, y):
	if button_down:
		view.drag(x, view.get_height() - y)
	glutPostRedisplay()

def reshapeFun(w, h):
	glViewport(0, 0, w, h)
	glMatrixMode(GL_PROJECTION)
	glLoadIdentity()
	gluOrtho2D(0.0, w, 0.0, h)
	glMatrixMode(GL_MODELVIEW)

	view.set_dimensions(w, h)

calibrate_rq = False

def keyPressedFun(key, x, y):
	global calibrate_rq
	if key == 'c':
		calibrate_rq = True

wf_inserts = Queue.Queue()
wf_edge = 0

def idleFun():
	global wf_edge

	try:
		while not wf_inserts.empty():
			rec = wf_inserts.get_nowait()
			multitexture.insert(wf_edge, rec)

			wf_edge += 1
			if wf_edge >= multitexture.get_height():
				wf_edge = 0
	except Queue.Empty:
		return

def process():
	global mag_a, mag_b, calibrate_rq

	while True:
		signal = sig_input.read(bins)
		spectrum = np.log(np.absolute(np.fft.fft(np.multiply(signal, window))))
		spectrum = np.concatenate((spectrum[bins/2:bins], spectrum[0:bins/2]))

		if calibrate_rq:
			calibrate_rq = False

			a = int(((-view.origin_x) / view.scale_x + 1) / 2 * bins)
			b = int(((-view.origin_x + view.width) / view.scale_x + 1) / 2 * bins)

			a = max(0, min(bins - 1, a))
			b = max(0, min(bins - 1, b))

			if a != b:
				area = spectrum[a:b]
				mag_a = np.min(area) - 0.5
				mag_b = np.max(area) + 1.0

		scale = 2.75 / (mag_b - mag_a)
		shift = -mag_a * scale - 1.75

		line = pysdrext.mag2col((spectrum * scale + shift).astype('f'))
		wf_inserts.put(line)

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Plot live spectral waterfall of an IQ signal.')
	parser.add_argument('-b', '--bins', type=int, default=4096,
						help='number of bins')
	parser.add_argument('-j', '--jack', metavar='NAME', default='pysdr',
						help='feed signal from JACK under the given name')
	parser.add_argument('-r', '--raw', metavar='RATE', type=int,
						help='feed signal from the standard input, 2 channel \
								interleaved floats with the given samplerate')

	args = parser.parse_args()

	bins = args.bins
	window = 0.5 * (1.0 - np.cos((2 * math.pi * np.arange(bins)) / bins))

	if args.raw:
		sig_input = RawSigInput(args.raw, 2, np.dtype(np.float32), sys.stdin)
	else:
		sig_input = JackInput(args.jack)

	glutInit()
	glutInitWindowSize(640, 480)
	glutCreateWindow('PySDR')
	glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_MULTISAMPLE)
	glutDisplayFunc(displayFun)
	glutIdleFunc(idleFun)
	glutMouseFunc(mouseFun)
	glutMotionFunc(motionFun)
	glutReshapeFunc(reshapeFun)
	glutKeyboardFunc(keyPressedFun)

	if bins % 1024 != 0:
		raise NotImplementedError("bins must be multiply of 1024")

	multitexture = MultiTexture(1024, 1024, bins / 1024, 4)
	overlay = PlotOverlay(view, sig_input)

	initFun()

	process_t = threading.Thread(target=process)
	process_t.start()

	sig_input.start()

	glutMainLoop()
