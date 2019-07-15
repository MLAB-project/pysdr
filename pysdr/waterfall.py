#!/usr/bin/python

import math
import sys
import Queue
import threading
import numpy as np
import argparse

from OpenGL.GL import *
from OpenGL.GLU import *

from OpenGL.GLUT import GLUT_LEFT_BUTTON, GLUT_RIGHT_BUTTON, GLUT_UP, GLUT_DOWN

from pysdr.graph import MultiTexture, PlotLine
from pysdr.input import RawSigInput, JackInput
from pysdr.overlay import View, PlotAxes, static_axis, UNIT_HZ, UNIT_SEC, _axis
from pysdr.console import Console
from pysdr.commands import make_commands_layer
from pysdr.events import EventMarker, DetectorScript, MIDIEventGatherer
import pysdr.ext as ext


class Viewer:
    def __init__(self):
        self.view = View()
        self.buttons_pressed = []

        self.layers = [self, self.view]

    def draw_string(self, x, y, string):
        return
        glWindowPos2i(int(x), int(y))
        for c in string:
            glutBitmapCharacter(GLUT_BITMAP_8_BY_13, ord(c))

    def gl_init(self):
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

    def gl_draw(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glClearColor(0, 0, 0, 1)
        glLoadIdentity()

        glPushMatrix()
        self.view.setup()
        self.call_layers('draw_content')
        glPopMatrix()

        self.call_layers('draw_screen')

    def mouse_btn(self, left, down, x, y):
        print left, down, x, y

        if down:
            self.buttons_pressed.append(left)
        else:
            try:
                self.buttons_pressed.remove(left)
            except ValueError:
                pass

        self.call_layers_handler('on_mouse_button', (GLUT_LEFT_BUTTON if left else GLUT_RIGHT_BUTTON,
                                                     GLUT_DOWN if down else GLUT_UP, x, y))

    def mouse_motion(self, x, y):
        if len(self.buttons_pressed) == 0:
            return

        self.call_layers_handler('on_drag', (x, y))

    def gl_reshape(self, w, h):
        print w, h
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0.0, w, 0.0, h)
        glMatrixMode(GL_MODELVIEW)

        self.screen_size = (w, h)

        self.call_layers('on_resize', (w, h))

    def key_press(self, key):
        self.call_layers_handler('on_key_press', (key))

    def get_layer(self, type):
        a = [a for a in self.layers if a.__class__ == type]
        return a[0] if len(a) else None

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

class WaterfallWindow(Viewer):
    def __init__(self, sig_input, bins, overlap=0, **kwargs):
        if bins % 1024 != 0:
            raise NotImplementedError("number of bins must be a multiple of 1024")

        Viewer.__init__(self)

        self.mag_range = (-45, 5)

        self.sig_input = sig_input
        self.bins = bins
        self.window = 0.5 * (1.0 - np.cos((2 * math.pi * np.arange(self.bins)) / self.bins))
        self.overlap = overlap
        self.row_duration = float(bins - overlap) / sig_input.sample_rate
        self.multitexture = MultiTexture(1024, 1024, self.bins / 1024, 1)

        def time_axis(a, b):
            scale = self.row_duration * self.multitexture.get_height()
            return _axis(a, b, scale, self.row_duration * self.texture_row - scale,
                         UNIT_SEC, (0.0, 1.0))

        self.overlay = PlotAxes(self, static_axis(UNIT_HZ, sig_input.sample_rate / 2,
                                                  cutoff=(-1.0, 1.0)), time_axis)
        self.layers.append(self.overlay)

        self.texture_inserts = Queue.Queue()
        self.texture_edge = 0

        self.texture_row = 0
        self.process_row = 0

        self.process_thread = threading.Thread(target=self.process)
        self.process_thread.setDaemon(True)

    def start(self):
        self.sig_input.start()
        self.process_thread.start()

    def gl_init(self):
        Viewer.gl_init(self)
        self.multitexture.gl_init()
        glLineWidth(1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def draw_content(self):
        while True:
            try:
                rec = self.texture_inserts.get(block=False)
                self.multitexture.insert(self.texture_edge, rec)
                self.texture_row = self.texture_row + 1
                self.texture_edge = self.texture_row % self.multitexture.get_height()
                self.call_layers('on_texture_insert')
            except Queue.Empty:
                break

        glPushMatrix()
        glTranslated(-1.0, 0.0, 0.0)
        glScalef(2.0, 1.0, 1.0)
        self.multitexture.draw_scroll(self.texture_edge)
        glPopMatrix()

    def freq_to_bin(self, freq):
        return int(freq * self.bins / self.sig_input.sample_rate + self.bins / 2)

    def bin_to_freq(self, bin):
        return float(bin - self.bins / 2) / self.bins * self.sig_input.sample_rate

    def bin_to_x(self, bin):
        return float(bin) / self.bins * 2 - 1

    def row_to_y(self, row):
        return float(row - self.texture_row) / self.multitexture.get_height() + 1.0

    def req_update(self):
        pass

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

            try:
                scale = 3.75 / (self.mag_range[1] - self.mag_range[0])
            except ZeroDivisionError:
                scale = 3.75 / 0.00001

            shift = -self.mag_range[0] * scale - 1.75

            line = ext.mag2col((spectrum * scale + shift).astype('f'))
            self.process_row = self.process_row + 1
            self.texture_inserts.put(line)
            self.req_update()

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
        glPushMatrix()
        glTranslatef(x, y, 0)
        self.viewer.draw_text(self.content)
        glPopMatrix()
        #Console.draw_string(x, y, self.content)


#def glut_loop(what_to_loop_on):
#    from OpenGL.GLUT import *
#    glutInit()
#    glutInitWindowSize(640, 480)
#    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA)
#
#    glutCreateWindow(window_name)
#
#    def display_func():
#        what_to_loop_on.gl_draw()
#        glutSwapBuffers()
#
#    glutDisplayFunc(display_func)
#
#    def mouse_func(button, state, x, y):
#        what_to_loop_on.mouse_btn(button == GLUT_LEFT_BUTTON,
#                                  state == GLUT_DOWN,
#                                  x, y)
#        glutPostRedisplay()
#
#    glutMouseFunc(mouse_func)
#
#    def motion_func(x, y):
#        what_to_loop_on.motion_func(x, y)
#        glutPostRedisplay()
#
#    glutMotionFunc(motion_func)
#
#    glutReshapeFunc(what_to_loop_on.gl_reshape)
#    glutKeyboardFunc(lambda key, x, y: what_to_loop_on.key_press)
#
#    what_to_loop_on.gl_init()
#
#    glutMainLoop()


import sdl2
import sdl2.ext

pybuf_from_memory = ctypes.pythonapi.PyBuffer_FromReadWriteMemory
pybuf_from_memory.restype = ctypes.py_object

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

font_manager = sdl2.ext.FontManager(FONT_PATH, size=12)
text_cache = dict()

def render_text(text):
    if text not in text_cache:
        surface = font_manager.render(text)

        texture = glGenTextures(1)

        a = np.zeros((surface.h, surface.w), dtype=np.uint32)
        a[:,:] = sdl2.ext.pixels2d(surface).transpose()

        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, surface.w, surface.h, 0,
                     GL_BGRA, GL_UNSIGNED_INT_8_8_8_8_REV, a)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR) # TODO: gl prefix?
        glDisable(GL_TEXTURE_2D)
        text_cache[text] = {'surf': surface, 'text': texture}

    surf = text_cache[text]['surf']
    texture = text_cache[text]['text']

    glColor4f(1.0, 1.0, 1.0, 1.0)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture)

    glBegin(GL_QUADS)
    glTexCoord2i(0, 1)
    glVertex2i(0, 0)
    glTexCoord2i(0, 0)
    glVertex2i(0, surf.h)
    glTexCoord2i(1, 0)
    glVertex2i(surf.w, surf.h)
    glTexCoord2i(1, 1)
    glVertex2i(surf.w, 0)
    glEnd()

    glDisable(GL_TEXTURE_2D)

def sdl2_window_loop(w, h, name, cont):
    UPDATE_REQ_EVENT = sdl2.SDL_RegisterEvents(1)

    def req_update():
        event = sdl2.SDL_Event()
        event.type = UPDATE_REQ_EVENT
        sdl2.SDL_PushEvent(ctypes.byref(event))

    sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)

    window = sdl2.SDL_CreateWindow(name,
                                   sdl2.SDL_WINDOWPOS_CENTERED,
                                   sdl2.SDL_WINDOWPOS_CENTERED, w, h,
                                   sdl2.SDL_WINDOW_RESIZABLE | sdl2.SDL_WINDOW_OPENGL)
    context = sdl2.SDL_GL_CreateContext(window)

    cont.draw_text = render_text
    cont.req_update = req_update

    cont.gl_init()
    cont.gl_reshape(w, h)

    event = sdl2.SDL_Event()
    while True:
        sdl2.SDL_WaitEvent(ctypes.byref(event))

        while True:
            if event.type == sdl2.SDL_QUIT:
                return

            if event.type in (sdl2.SDL_MOUSEBUTTONDOWN, sdl2.SDL_MOUSEBUTTONUP, sdl2.SDL_MOUSEMOTION):
                event.motion.y = h - event.motion.y

            if event.type in (sdl2.SDL_MOUSEBUTTONDOWN, sdl2.SDL_MOUSEBUTTONUP):
                cont.mouse_btn((event.motion.state & sdl2.SDL_BUTTON_LEFT),
                               event.type == sdl2.SDL_MOUSEBUTTONDOWN,
                               event.motion.x, event.motion.y)
    
            if event.type == sdl2.SDL_MOUSEMOTION:
                cont.mouse_motion(event.motion.x, event.motion.y)
    
            if event.type == sdl2.SDL_WINDOWEVENT and event.window.event == sdl2.SDL_WINDOWEVENT_RESIZED:
                w, h = event.window.data1, event.window.data2
                cont.gl_reshape(w, h)

            if sdl2.SDL_PollEvent(ctypes.byref(event)) == 0:
                break

        cont.gl_draw()
        sdl2.SDL_GL_SwapWindow(window)


def main():
    parser = argparse.ArgumentParser(description='Plot live spectral waterfall of a quadrature signal.')
    parser.add_argument('-b', '--bins', type=int, default=4096,
                        help='number of FFT bins (default: %(default)s)')
    parser.add_argument('-H', '--height', type=float, default=0,
                        help='minimal height of the waterfall in seconds (default 1024 FFT rows)')
    parser.add_argument('-o', '--overlap', type=float, default=0.75,
                        help='overlap between consecutive windows as a proportion \
                                of the number of bins (default: %(default)s)')
    parser.add_argument('-j', '--jack', metavar='NAME', default='pysdr',
                        help='feed signal from JACK and use the given client name \
                                (by default, with name \'pysdr\')')
    parser.add_argument('-r', '--raw', metavar='RATE', type=int,
                        help='feed signal from the standard input, 2 channel \
                                interleaved floats with the given samplerate')
    parser.add_argument('-d', '--detector', metavar='FILENAME', action='append', \
                        help='attach the given detector script')

    args = parser.parse_args()

    overlap_bins = int(args.bins * args.overlap)

    if not (overlap_bins >= 0 and overlap_bins < args.bins):
        raise ValueError("number of overlapping bins is out of bounds")

    if args.raw:
        sig_input = RawSigInput(args.raw, 2, np.dtype(np.float32), sys.stdin)
    else:
        sig_input = JackInput(args.jack)

    viewer = WaterfallWindow(sig_input, args.bins, overlap=overlap_bins)

    if args.detector:
        detector_em = EventMarker(viewer)
        viewer.layers.append(detector_em)
        viewer.layers += [DetectorScript(viewer, [detector_em], fn) for fn in args.detector]

    if isinstance(sig_input, JackInput):
        midi_em = EventMarker(viewer)
        viewer.layers += [midi_em, MIDIEventGatherer(viewer, [midi_em])]

    viewer.layers += [make_commands_layer(viewer), RangeSelector(viewer),
                      Label(viewer, str(viewer.sig_input)), Console(viewer, locals())]

    viewer.start()

    sdl2_window_loop(640, 480, "pysdr pysdr pysdr", viewer)

if __name__ == "__main__":
    main()
