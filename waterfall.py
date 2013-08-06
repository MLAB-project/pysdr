import math
import sys
import subprocess
import Queue
import threading
import numpy as np

from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

from graph import *
from input import *
from overlay import *

sys.path.append("./pysdrext/pysdrext_directory")
import pysdrext

bins = 4096

process = subprocess.Popen(['arecord', '-c', '2', '-f', 'FLOAT_LE',
				'-r', '64000', '--buffer-size', str(bins)],
			shell=False, stdin=None, stdout=subprocess.PIPE)
sig_input = RawSigInput(64000, 2, np.dtype(np.float32), process.stdout)

window = 0.5 * (1.0 - np.cos((2 * math.pi * np.arange(bins)) / bins))

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
	while True:
		signal = sig_input.read(bins)
		spectrum = np.log(np.absolute(np.fft.fft(np.multiply(signal, window))))
		spectrum = np.concatenate((spectrum[bins/2:bins], spectrum[0:bins/2]))

		scale = 2.75 / (mag_b - mag_a)
		shift = -mag_a * scale - 1.75

		line = pysdrext.mag2col((spectrum * scale + shift).astype('f'))
		wf_inserts.put(line)

if __name__ == "__main__":
	glutInit()
	glutInitWindowSize(640, 480)
	glutCreateWindow('PySDR')
	glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_MULTISAMPLE)
	glutDisplayFunc(displayFun)
	glutIdleFunc(idleFun)
	glutMouseFunc(mouseFun)
	glutMotionFunc(motionFun)
	glutReshapeFunc(reshapeFun)

	if bins % 2048 != 0:
		raise NotImplementedError("bins must be multiply of 2048")

	multitexture = MultiTexture(2048, 512, bins / 2048, 8)
	overlay = PlotOverlay(view, sig_input)

	initFun()

	process_t = threading.Thread(target=process)
	process_t.start()

	glutMainLoop()
