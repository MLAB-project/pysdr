#!/usr/bin/python

# Experimental record viewer, recalculates the waterfall
# with different number of bins according to its visual stretching.

import numpy as np
import Queue as queue
import threading
import scipy.io.wavfile
import sys

from OpenGL.GL import *
from OpenGL.GLUT import *

from waterfall import *

import ext

class AsyncWorker(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = False
        self.working = False
        self.event = threading.Event()
        self.start()

    def set_work(self, func, args):
        self.work = (func, args)
        self.event.set()

    def run(self):
        while True:
            self.event.wait()
            self.event.clear()
            self.working = True
            (func, args) = self.work
            func(*args)
            self.working = False

def waterfallize(signal, bins):
    window = 0.5 * (1.0 - np.cos((2 * math.pi * np.arange(bins)) / bins))
    segment = bins / 2
    nsegments = int(len(signal) / segment)
    rows = nsegments - 1
    m = np.repeat(np.reshape(signal[0:segment * nsegments], (nsegments, segment)), 2, axis=0)
    t = np.reshape(m[1:len(m) - 1], (rows, bins))
    img = np.multiply(t, window)

    return np.log(np.abs(np.fft.fft(img)))

class RecordViewer(Viewer):
    def __init__(self, signal):
        Viewer.__init__(self, "Record Viewer")
        glutIdleFunc(self.cb_idle)
        self.signal = signal
        self.bins = None
        self.texture = None
        self.new_data_event = threading.Event()
        self.new_data = None
        self.worker = AsyncWorker()
        self.update_texture()

    def update_texture(self):
        bins = int(int(np.sqrt(len(self.signal) / self.view.scale_y * self.view.scale_x)) / 16) * 16
        bins = min(max(bins, 16), glGetIntegerv(GL_MAX_TEXTURE_SIZE))

        if bins == self.bins:
            return

        def texture_work(self, bins):
            waterfall = waterfallize(self.signal, bins)
            waterfall = ((waterfall - np.min(waterfall)) / (np.max(waterfall) - np.min(waterfall))) * 5.5 - 4.5
            self.new_data = ext.mag2col(waterfall.astype('f'))
            self.new_data_event.set()

        self.worker.set_work(texture_work, (self, bins))

    def on_mouse_button(self, button, state, x, y):
        if state == GLUT_UP and button == GLUT_RIGHT_BUTTON:
            self.update_texture()

    def cb_idle(self):
        if self.new_data_event.wait(0.01):
            self.new_data_event.clear()

            try:
                self.texture = Texture(self.new_data)
            except GLError:
                pass

            self.new_data = None
            glutPostRedisplay()

    def draw_content(self):
        if self.texture != None:
            glColor4f(1.0, 1.0, 1.0, 1.0)
            self.texture.draw()

    def draw_screen(self):
        if self.worker.working:
            glColor4f(1.0, 0.0, 0.0, 1.0)
            glBegin(GL_QUADS)
            glVertex2i(10, 10)
            glVertex2i(20, 10)
            glVertex2i(20, 20)
            glVertex2i(10, 20)
            glEnd()

def view(signal):
    glutInit()
    glutInitWindowSize(640, 480)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA)

    record_viewer = RecordViewer(signal)

    glutMainLoop()

def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: recordviewer.py WAV_FILENAME\n")
        exit(1)

    audio = scipy.io.wavfile.read(sys.argv[1])[1]
    signal = audio[:,0] + audio[:,1] * 1j
    view(signal)

if __name__ == "__main__":
    main()
