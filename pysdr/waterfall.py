#!/usr/bin/python

import math
import sys
import Queue
import threading
import numpy as np
import argparse
import signal
import time

from OpenGL.GL import *
from OpenGL.GL import shaders
from OpenGL.GLUT import *
from OpenGL.GLU import *

from pysdr.graph import MultiTexture, PlotLine
from pysdr.input import RawSigInput, JackInput
from pysdr.overlay import View, PlotAxes, static_axis, UNIT_HZ, UNIT_SEC, _axis, time_of_day_axis
from pysdr.console import Console
from pysdr.commands import make_commands_layer
from pysdr.events import EventMarker, DetectorScript, MIDIEventGatherer
from pysdr.persistence import pers_load, pers_save
import pysdr.ext as ext

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

    def call_layers(self, method, args=()):
        for layer in list(self.layers):
            if hasattr(layer.__class__, method):
                getattr(layer, method)(*args)

    def call_layers_handler(self, method, args=()):
        for layer in list(reversed(self.layers)):
            if hasattr(layer.__class__, method):
                if getattr(layer, method)(*args):
                    break

    def cb_display(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glClearColor(0, 0, 0, 1)
        glLoadIdentity()

        glPushMatrix()
        self.view.setup()
        self.call_layers('draw_content')
        glPopMatrix()

        self.call_layers('draw_screen')

        glutSwapBuffers()

    def cb_mouse(self, button, state, x, y):
        if state == GLUT_DOWN:
            self.buttons_pressed.append(button)

        if state == GLUT_UP:
            try:
                self.buttons_pressed.remove(button)
            except ValueError:
                pass

        self.call_layers_handler('on_mouse_button', (button, state, x,
                                                     self.screen_size[1] - y))

        glutPostRedisplay()

    def cb_motion(self, x, y):
        if len(self.buttons_pressed) == 0:
            return

        self.call_layers_handler('on_drag', (x, self.screen_size[1] - y))

        glutPostRedisplay()

    def cb_reshape(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0.0, w, 0.0, h)
        glMatrixMode(GL_MODELVIEW)

        self.screen_size = (w, h)

        self.call_layers('on_resize', (w, h))

    def cb_keyboard(self, key, x, y):
        self.call_layers_handler('on_key_press', (key))
        glutPostRedisplay()

    def get_layer(self, type):
        a = [a for a in self.layers if a.__class__ == type]
        return a[0] if len(a) else None

class Texture():
    def __init__(self, image):
        self.texture = glGenTextures(1)

        glEnable(GL_TEXTURE_2D)

        glBindTexture(GL_TEXTURE_2D, self.texture)

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)

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
        self.texture = Texture(ext.mag2col((np.arange(64, dtype=np.float32) / 64)
                                           * 3.75 - 1.75).reshape((64, 1)))
        self.viewer = viewer
        self.histogram = PlotLine(90)
        self.hist_range = (-60, 20)
        self.dragging = None

    def mag_to_pixel(self, mag):
        return int((float(mag) - self.hist_range[0])
                   / (self.hist_range[1] - self.hist_range[0]) * 180)

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
        glScalef(180, -70.0 / self.viewer.bins, 1)
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
            pix_a, pix_b = [self.mag_to_pixel(l) for l in self.viewer.mag_range]

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

class ColorMappingShader:
    VERT_SHADER_CODE = """
        #version 120
        void main() {
            gl_TexCoord[0] = gl_MultiTexCoord0;
            gl_Position = ftransform();
        }
    """

    FRAG_SHADER_CODE = """
        #version 120
        uniform float scale;
        uniform float shift;
        uniform sampler2D sampler;

        float mag2col_base2_blue(float val)
        {
            if (val <= -2.75)
                return 0.0;

            if (val <= -1.75)
                return val + 2.75;

            if (val <= -0.75)
                return -(val + 0.75);

            if (val <= 0.0)
                return 0.0;

            if (val >= 1.0)
                return 1.0;

            return val;
        }

        vec3 mag2col(float a) {
            return vec3(clamp(a + 1.0, 0.0, 1.0), clamp(a, 0.0, 1.0),
                        mag2col_base2_blue(a - 1.0));
        }

        void main() {
            gl_FragColor = vec4(mag2col((texture2D(sampler, gl_TexCoord[0].xy).x + shift) * scale), 1);
        }
    """

    M2C_RANGE = (-1.75, 2.)
    TEX_RANGE = (-100., 60.)

    def setup(self, mag_range):
        scale = (self.TEX_RANGE[1] - self.TEX_RANGE[0]) / (mag_range[1] - mag_range[0]) * (self.M2C_RANGE[1] - self.M2C_RANGE[0])
        shift = (self.TEX_RANGE[0] - mag_range[0]) / (self.TEX_RANGE[1] - self.TEX_RANGE[0]) + self.M2C_RANGE[0] / scale

        shaders.glUseProgram(self.program)

        glUniform1i(glGetUniformLocation(self.program, "sampler"), 0)
        glUniform1f(glGetUniformLocation(self.program, "scale"), scale)
        glUniform1f(glGetUniformLocation(self.program, "shift"), shift)
        glActiveTexture(GL_TEXTURE0)

    def texture_insert_prep(self, line):
        return (line - self.TEX_RANGE[0]) / (self.TEX_RANGE[1] - self.TEX_RANGE[0])

    def __init__(self):
        vert_shader = shaders.compileShader(self.VERT_SHADER_CODE, GL_VERTEX_SHADER)
        frag_shader = shaders.compileShader(self.FRAG_SHADER_CODE, GL_FRAGMENT_SHADER)
        self.program = shaders.compileProgram(vert_shader, frag_shader)


class WaterfallWindow(Viewer):
    def __init__(self, sig_input, bins, overlap=0, start_time=None):
        if bins % 1024 != 0:
            raise NotImplementedError("number of bins must be a multiple of 1024")

        Viewer.__init__(self, "PySDR")
        glutIdleFunc(self.cb_idle)

        self.mag_range = (-45, 5)

        self.sig_input = sig_input
        self.bins = bins
        self.window = 0.5 * (1.0 - np.cos((2 * math.pi * np.arange(self.bins)) / self.bins))
        self.overlap = overlap
        self.row_duration = float(bins - overlap) / sig_input.sample_rate
        # TODO: can we be sure the texture will be stored as floats internally?
        self.multitexture = MultiTexture(1024, 1024, self.bins / 1024, 1, format=GL_RED, type=GL_FLOAT)

        self.start_time = time.time() if start_time is None else start_time

        def time_axis(a, b):
            scale = self.row_duration * self.multitexture.get_height()
            shift = self.row_duration * self.texture_row - scale + self.start_time % (3600 * 24)
            return time_of_day_axis(a, b, scale, shift, UNIT_SEC, (0.0, 1.0))

        self.overlay = PlotAxes(self, static_axis(UNIT_HZ, sig_input.sample_rate / 2,
                                                  cutoff=(-1.0, 1.0)), time_axis)
        self.layers.append(self.overlay)

        self.texture_inserts = Queue.Queue()
        self.texture_edge = 0

        self.texture_row = 0
        self.process_row = 0

        self.process_thread = threading.Thread(target=self.process)
        self.process_thread.setDaemon(True)

        self.shader = ColorMappingShader()

    def start(self):
        self.sig_input.start()
        self.process_thread.start()

    def init(self):
        glLineWidth(1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def draw_content(self):
        glPushMatrix()
        glTranslated(-1.0, 0.0, 0.0)
        glScalef(2.0, 1.0, 1.0)

        self.shader.setup(self.mag_range)
        self.multitexture.draw_scroll(self.texture_edge)
        shaders.glUseProgram(0)
        glPopMatrix()

    def freq_to_bin(self, freq):
        return int(freq * self.bins / self.sig_input.sample_rate + self.bins / 2)

    def bin_to_freq(self, bin):
        return float(bin - self.bins / 2) / self.bins * self.sig_input.sample_rate

    def bin_to_x(self, bin):
        return float(bin) / self.bins * 2 - 1

    def row_to_y(self, row):
        return float(row - self.texture_row) / self.multitexture.get_height() + 1.0

    def cb_idle(self):
        try:
            while True:
                rec = self.texture_inserts.get(block=True, timeout=0.01)
                self.multitexture.insert(self.texture_edge, rec, format=GL_RED, type=GL_FLOAT)
                self.texture_row = self.texture_row + 1
                self.texture_edge = self.texture_row % self.multitexture.get_height()

                self.call_layers('on_texture_insert')

                glutPostRedisplay()
        except Queue.Empty:
            return

    def process(self):
        ringbuf = np.zeros(self.bins * 4, dtype=np.complex64)
        ringbuf_edge = self.bins
        readsize = self.bins - self.overlap

        while True:
            if (ringbuf_edge + readsize > len(ringbuf)):
                ringbuf[0:self.overlap] = ringbuf[ringbuf_edge - self.overlap:ringbuf_edge]
                ringbuf_edge = self.overlap

            ringbuf[ringbuf_edge:ringbuf_edge + readsize] = self.sig_input.read(readsize)
            ringbuf_edge += readsize

            signal = ringbuf[ringbuf_edge - self.bins:ringbuf_edge]

            spectrum = np.absolute(np.fft.fft(np.multiply(signal, self.window)))
            spectrum = np.concatenate((spectrum[self.bins/2:self.bins], spectrum[0:self.bins/2]))

            self.call_layers('on_lin_spectrum', (spectrum,))
            spectrum = np.log10(spectrum) * 10
            self.call_layers('on_log_spectrum', (spectrum,))

            #try:
            #    scale = 3.75 / (self.mag_range[1] - self.mag_range[0])
            #except ZeroDivisionError:
            #    scale = 3.75 / 0.00001

            #shift = -self.mag_range[0] * scale - 1.75

            #line = ext.mag2col((spectrum * scale + shift).astype('f'))
            line = self.shader.texture_insert_prep(spectrum).astype('f')
            self.process_row = self.process_row + 1
            self.texture_inserts.put(line)

class Label:
    @staticmethod
    def draw_bg(x, y, w, h, padding=0):
        x, y = x - padding, y - padding
        w, h = w + 2 * padding, h + 2 * padding

        glColor4f(0.0, 0.0, 0.0, 0.5)
        glBegin(GL_QUADS)
        glVertex2i(x + w, y)
        glVertex2i(x + w, y + h)
        glVertex2i(x, y + h)
        glVertex2i(x, y)
        glEnd()

    def __init__(self, viewer, content):
        self.viewer = viewer
        self.content = content

    def draw_screen(self):
        w, h = self.viewer.screen_size
        x, y = 10, h - Console.CHAR_HEIGHT - 10

        self.draw_bg(x, y - 2, Console.CHAR_WIDTH * len(self.content),
                     Console.CHAR_HEIGHT, padding=3)

        glColor4f(1.0, 1.0, 1.0, 0.75)
        Console.draw_string(x, y, self.content)

class DateLabel:
    def __init__(self, viewer):
        self.viewer = viewer

    def draw_screen(self):
        d = "2015-05-22"
        strlen = len(d)

        w, h = self.viewer.screen_size
        x, y = w - 10 - strlen * Console.CHAR_WIDTH, 10 + Console.CHAR_HEIGHT
        Label.draw_bg(x, y - 2, Console.CHAR_WIDTH * strlen, Console.CHAR_HEIGHT, padding=3)

        glColor4f(1.0, 1.0, 1.0, 1.0)
        Console.draw_string(x, y, d)

def main():
    global viewer # so that it can be accessed from the embedded console

    signal.signal(signal.SIGINT, lambda a, b: sys.exit(0))

    parser = argparse.ArgumentParser(description='Plot live spectral waterfall of a quadrature signal.')
    parser.add_argument('-b', '--bins', type=int, default=4096,
                        help='number of FFT bins (default: %(default)s)')
    parser.add_argument('-H', '--height', type=float, default=0,
                        help='minimal height of the waterfall in seconds \
                                (default corresponds to 1024 windows)')
    parser.add_argument('-o', '--overlap', type=float, default=0.75,
                        help='overlap between consecutive windows as a proportion \
                                of the number of bins (default: %(default)s)')
    parser.add_argument('-j', '--jack', metavar='NAME', default='pysdr',
                        help='feed signal from JACK and use the given client name \
                                (by default, with name \'pysdr\')')
    parser.add_argument('-r', '--raw', metavar='RATE', type=int,
                        help='feed signal from the standard input, expects 2 channel \
                                interleaved floats with the given sample-rate')
    parser.add_argument('-d', '--detector', metavar='ARGS', action='append',
                        help='attach the given detector script, \
                                expects to be given the script filename \
                                followed by arguments for the script, \
                                all joined by spaces and passed on the command-line \
                                as one quoted argument')
    parser.add_argument('-p', '--persfn', metavar='FILENAME',
                        help='a file in which to preserve the visualization parameters \
                                that come from interactive manipulation, \
                                i.e. the visible area of the waterfall \
                                and the selected magnitude range \
                                (save triggered by pressing \'p\')')

    args = parser.parse_args()

    overlap_bins = int(args.bins * args.overlap)

    if not (overlap_bins >= 0 and overlap_bins < args.bins):
        raise ValueError("number of overlapping bins is out of bounds")

    if args.raw is not None:
        sig_input = RawSigInput(args.raw, 2, np.dtype(np.float32), sys.stdin)
    else:
        sig_input = JackInput(args.jack)

    glutInit()
    glutInitWindowSize(640, 480)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA)

    viewer = WaterfallWindow(sig_input, args.bins, overlap=overlap_bins)

    if args.detector:
        detector_em = EventMarker(viewer)
        viewer.layers.append(detector_em)
        viewer.layers += [DetectorScript(viewer, [detector_em], a.split()) for a in args.detector]

    if isinstance(sig_input, JackInput):
        midi_em = EventMarker(viewer)
        viewer.layers += [midi_em, MIDIEventGatherer(viewer, [midi_em])]

    viewer.layers += [make_commands_layer(viewer), RangeSelector(viewer),
                      Label(viewer, str(viewer.sig_input)),
# TODO
#                      DateLabel(viewer),
                      Console(viewer, globals())]

    if args.persfn is not None:
        viewer.persfn = args.persfn
        pers_load(viewer, args.persfn)

    viewer.start()

    glutMainLoop()

if __name__ == "__main__":
    main()
