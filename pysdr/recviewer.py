#!/usr/bin/python

# Experimental record viewer, recalculates the waterfall
# with different number of bins according to its visual stretching.

import numpy as np
import Queue as queue
import threading
import scipy.io.wavfile
import sys
import os.path

from OpenGL.GL import *
from OpenGL.GLUT import *

from pysdr.waterfall import *
from pysdr.overlay import *
import pysdr.ext as ext

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
    m = np.repeat(np.reshape(signal[0:segment * nsegments], (nsegments, segment)), 2, axis=0)
    t = np.reshape(m[1:len(m) - 1], (nsegments - 1, bins))
    img = np.multiply(t, window)
    wf = np.log(np.abs(np.fft.fft(img)))
    return np.concatenate((wf[:, bins / 2:bins], wf[:, 0:bins / 2]), axis=1)

class RecordViewer(Viewer):
    def __init__(self, signal, sample_rate=None):
        Viewer.__init__(self, "Record Viewer")

        if sample_rate is not None:
            # TODO: cutting off trailing frames in waterfallize
            #       probably causes time axis to be a bit off
            duration = float(len(signal)) / sample_rate
            self.layers.append(PlotAxes(self, static_axis(UNIT_HZ, sample_rate / 2,
                                                          cutoff=(-1.0, 1.0)),
                                        static_axis(UNIT_SEC, -duration, offset=duration)))

        glutIdleFunc(self.cb_idle)
        self.signal = signal
        self.bins = None
        self.texture = None
        self.new_data_event = threading.Event()
        self.new_data = None
        self.worker = AsyncWorker()
        self.update_texture()

    def init(self):
        glLineWidth(1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def update_texture(self):
        bins = int(int(np.sqrt(len(self.signal) / self.view.scale_y * self.view.scale_x)) / 16) * 16
        bins = min(max(bins, 16), glGetIntegerv(GL_MAX_TEXTURE_SIZE))

        if bins == self.bins:
            return

        def texture_work(self, bins):
            waterfall = waterfallize(self.signal, bins)
            waterfall[np.isneginf(waterfall)] = np.nan
            wmin, wmax = np.nanmin(waterfall), np.nanmax(waterfall)
            waterfall = ((waterfall - wmin) / (wmax - wmin)) * 5.5 - 4.5
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
            glPushMatrix()
            glTranslatef(-1.0, 0, 0)
            glScalef(2.0, 1.0, 1.0)
            glColor4f(1.0, 1.0, 1.0, 1.0)
            self.texture.draw()
            glPopMatrix()

    def draw_screen(self):
        if self.worker.working:
            glColor4f(1.0, 0.0, 0.0, 1.0)
            glBegin(GL_QUADS)
            glVertex2i(10, 10)
            glVertex2i(20, 10)
            glVertex2i(20, 20)
            glVertex2i(10, 20)
            glEnd()

def view(signal, sample_rate=None):
    glutInit()
    glutInitWindowSize(640, 480)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA)

    record_viewer = RecordViewer(signal, sample_rate=sample_rate)

    glutMainLoop()

def read_file(filename):
    ext = os.path.splitext(filename)[1]

    if ext == ".wav":
        import scipy.io.wavfile

        (sample_rate, audio) = scipy.io.wavfile.read(filename)
        return (sample_rate, audio[:,0] + 1j * audio[:,1])
    elif ext == ".fits":
        import pyfits
        img = pyfits.open(filename)[0]

        if int(img.header["NAXIS"]) != 2:
            raise Exception("expecting a two dimensional image")

        size = [img.header["NAXIS%d" % (i,)] for i in [1, 2]]

        if size[0] % 2 != 0:
            raise Exception("width %d is not a multiple of 2" % (size[0],))

        flat_data = np.ravel(img.data)
        return (48000, flat_data[0::2] + 1j * flat_data[1::2])
    else:
        raise Exception("unknown filename extension: %s" % (ext,))

def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: recordviewer.py FILENAME\n")
        exit(1)

    sample_rate, signal = read_file(sys.argv[1])
    view(signal, sample_rate=sample_rate)

if __name__ == "__main__":
    main()
