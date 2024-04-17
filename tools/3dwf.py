#!/usr/bin/python3
# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
import math
import gzip
import ctypes
import socket
import numpy as np

import os
os.environ['PYSDL2_DLL_PATH'] = '.'

import sdl2
import sdl2.ext

import OpenGL.GL as gl
try: 
    import queue
except ImportError:
    import Queue as queue

from OpenGL.GL import *
from OpenGL.GL import shaders
from OpenGL.GLU import gluOrtho2D
from OpenGL.arrays import vbo, GLOBAL_REGISTRY

import threading


if np.float32 not in GLOBAL_REGISTRY:
    from OpenGL.arrays.numpymodule import NumpyHandler
    NumpyHandler().register(np.float32)

pybuf_from_memory = ctypes.pythonapi.PyMemoryView_FromMemory
pybuf_from_memory.restype = ctypes.py_object


FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

font_manager = sdl2.ext.FontManager(FONT_PATH)
text_cache = dict()

def render_text(text):
    if text not in text_cache:
        surface = font_manager.render(text)

        texture = gl.glGenTextures(1)

        a = np.zeros((surface.h, surface.w), dtype=np.uint32)
        a[:,:] = sdl2.ext.pixels2d(surface).transpose()

        gl.glEnable(GL_TEXTURE_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, surface.w, surface.h, 0,
                        gl.GL_BGRA, gl.GL_UNSIGNED_INT_8_8_8_8_REV, a)
        gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR) # TODO: gl prefix?
        gl.glDisable(GL_TEXTURE_2D)
        text_cache[text] = {'surf': surface, 'text': texture}

    surf = text_cache[text]['surf']
    texture = text_cache[text]['text']

    gl.glColor4f(1.0, 1.0, 1.0, 1.0)
    gl.glEnable(gl.GL_TEXTURE_2D)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)

    gl.glBegin(GL_QUADS)
    glTexCoord2i(0, 1)
    gl.glVertex2i(0, 0)
    glTexCoord2i(0, 0)
    gl.glVertex2i(0, surf.h)
    glTexCoord2i(1, 0)
    gl.glVertex2i(surf.w, surf.h)
    glTexCoord2i(1, 1)
    gl.glVertex2i(surf.w, 0)
    gl.glEnd()

    gl.glDisable(gl.GL_TEXTURE_2D)


class Waterfall3D:
    def __init__(self, points, history=100):
        self.history = history
        self.points = points
        self.last_line = np.zeros(points, dtype=np.float32)
        self.vbo = vbo.VBO(np.zeros((points - 1) * 4 * self.history * 3,
                           dtype=np.float32), usage='GL_STREAM_DRAW_ARB')
        self.vbo_edge = 0
        self.nrows = 0

        vertex_shader = shaders.compileShader("""
            #version 130
            varying float height;
            void main() {
                height = gl_Vertex.z;
                gl_Position = ftransform();
            }
            """, gl.GL_VERTEX_SHADER)

        frag_shader = shaders.compileShader("""
            #version 130
            varying float height;
            uniform float scale;
            uniform float offset;

            float mag2col_base2(float val)
            {
                if (val <= 0.0)
                    return 0.0;
                if (val >= 1.0)
                    return 1.0;

                return val;
            }

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
                return vec3(mag2col_base2(a + 1.0), mag2col_base2(a),
                            mag2col_base2_blue(a - 1.0));
            }

            void main() {
                //gl_FragColor = vec4(height, 1 - height, height, 1 );
                gl_FragColor = vec4(mag2col(offset + height * scale), 1);
            }
            """, gl.GL_FRAGMENT_SHADER)
        self.shader = shaders.compileProgram(vertex_shader,frag_shader)

    def set(self, content):
        # TODO
        raise NotImplementedError

    def insert(self, line):
        vbo_edge = self.nrows % self.history

        strip_nvertices = (self.points - 1) * 4
        strip = np.zeros((strip_nvertices, 3), dtype=np.float32)
        strip[:,0] = np.repeat(np.arange(self.points, dtype=np.float32) / (self.points - 1), 4)[2:-2]
        strip[:,1] = np.tile((np.array([1.0, 0.0, 0.0, 1.0]) + vbo_edge) / self.history, self.points - 1)
        strip[0::4,2] = line[0:-1]
        strip[3::4,2] = line[1::]
        strip[1::4,2] = self.last_line[0:-1]
        strip[2::4,2] = self.last_line[1::]

        self.vbo[len(self.vbo) - (vbo_edge + 1) * strip_nvertices * 3 \
                 :len(self.vbo) - vbo_edge * strip_nvertices * 3] = strip.flatten()

        self.nrows = self.nrows + 1
        self.last_line = line

    def draw_scroll(self, offset, scale):
        glPushMatrix()

        shaders.glUseProgram(self.shader)

        glUniform1f(glGetUniformLocation(self.shader, "offset"), offset)
        glUniform1f(glGetUniformLocation(self.shader, "scale"), scale)

        self.vbo.bind()
        glColor4f(1.0, 0.0, 0.0, 1.0)
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointerf(None)

        vbo_edge = self.nrows % self.history
        strip_nvertices = (self.points - 1) * 4

        glPushMatrix()
        glTranslatef(0.0, -float(vbo_edge) / self.history, 0.0)
        glDrawArrays(GL_QUADS, strip_nvertices * (self.history - vbo_edge), strip_nvertices * vbo_edge)
        glPopMatrix()

        glPushMatrix()
        glTranslatef(0.0, -1.0 - float(vbo_edge) / self.history, 0.0)
        glDrawArrays(GL_QUADS, 0, strip_nvertices * (self.history - vbo_edge))
        glPopMatrix()

        glDisableClientState(GL_VERTEX_ARRAY)
        self.vbo.unbind()
        shaders.glUseProgram(0)

        glPopMatrix()

    def draw(self):
        glPushMatrix()

        shaders.glUseProgram(self.shader)
        self.vbo.bind()
        glColor4f(1.0, 0.0, 0.0, 1.0)
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointerf(None)

        vbo_edge = self.nrows % self.history
        strip_nvertices = (self.points - 1) * 4

        glDrawArrays(GL_QUADS, 0, strip_nvertices * self.history)
        glDisableClientState(GL_VERTEX_ARRAY)
        self.vbo.unbind()
        shaders.glUseProgram(0)

        glPopMatrix()

def rotate_vector(v, axis, theta_cos, theta_sin):
    va = axis * np.vdot(v, axis)
    y = v - va
    x = np.cross(axis, y)
    return va + y * theta_cos + x * theta_sin

def rotation_matrix(axis, theta):
    theta_cos, theta_sin = math.cos(theta), math.sin(theta)

    m = np.eye(4)
    m[0:3, 0] = rotate_vector(m[0:3, 0], axis, theta_cos, theta_sin)
    m[0:3, 1] = rotate_vector(m[0:3, 1], axis, theta_cos, theta_sin)
    m[0:3, 2] = rotate_vector(m[0:3, 2], axis, theta_cos, theta_sin)

    return m

def projection_matrix(fov, ratio, near, far):
    m = np.zeros((4, 4), dtype=np.float32)

    top = math.tan(math.radians(fov / 2))
    right = top * ratio

    m[0,0] = 1.0 / right
    m[1,1] = 1.0 / top
    m[2,2] = (far + near) / (near - far)
    m[2,3] = (2.0 * far * near) / (near - far)
    m[3,2] = -1

    return m

def scale_matrix(sx, sy, sz):
    m = np.eye(4)
    m[0,0] = sx; m[1,1] = sy; m[2,2] = sz;
    return m

def translation_matrix(tx, ty, tz):
    m = np.eye(4)
    m[0:3,3] = np.array([tx, ty, tz])
    return m

def normv(v):
    return v / np.linalg.norm(v)

def screen2world(m, x, y):
    a = np.dot(m, np.array([x, y, 1.0, 1.0]))
    return a[0:3] / a[3]

class Slider:
    def __init__(self, ori_x, ori_y, cb, text):
        self.sliding = False
        self.origin_x = ori_x
        self.origin_y = ori_y
        self.text = text
        self.cb = cb
        self.start_pos = 100
        self.pos = self.start_pos

    def draw(self):
        gl.glPushMatrix()

        gl.glTranslatef(self.origin_x, self.origin_y, 0)

        gl.glColor4f(1.0, 1.0, 1.0, 1.0)
        render_text(self.text)

#        gl.glPushMatrix()
#        gl.glTranslatef(self.pos - 100, 0, 0)
#        gl.glBegin(GL_LINES)
#        gl.glVertex2i(95, 14)
#        gl.glVertex2i(85, 10)
#        gl.glVertex2i(95, 6)
#        gl.glVertex2i(85, 10)
#
#        gl.glVertex2i(125, 14)
#        gl.glVertex2i(135, 10)
#        gl.glVertex2i(125, 6)
#        gl.glVertex2i(135, 10)
#        gl.glEnd()
#        gl.glPopMatrix()

        gl.glColor4f(0.7, 0.7, 0.7, 0.4)
        gl.glBegin(GL_QUADS)
        gl.glVertex2i(self.pos, 0)
        gl.glVertex2i(self.pos, 20)
        gl.glVertex2i(self.pos + 20, 20)
        gl.glVertex2i(self.pos + 20, 0)
        gl.glEnd()

        gl.glPopMatrix()

    def event(self, event):
        if self.sliding:
            if event.type == sdl2.SDL_MOUSEBUTTONUP:
                self.pos = self.start_pos
                self.sliding = False
                return True

            if event.type == sdl2.SDL_MOUSEMOTION:
                new_pos = self.start_pos + (event.motion.x - self.start_x)
                self.cb(new_pos - self.pos)
                self.pos = new_pos
                return True

        if event.type == sdl2.SDL_MOUSEBUTTONDOWN and (event.motion.state & sdl2.SDL_BUTTON_LEFT) \
                and self.origin_x + self.pos <= event.motion.x <= self.origin_y + self.pos + 20 \
                and self.origin_y <= event.motion.y <= 20 + self.origin_y:
            self.sliding = True
            self.start_x = event.motion.x
            return True

        return False

class WFViewer:
    def __init__(self, bins):
        self.view_inv = self.view = self.modelview = np.eye(4)
        self.waterfall = Waterfall3D(bins, history=500)
        self.inserts = queue.Queue()

        self.color_offset = 1.0
        self.color_scale = 1.0
        self.volume = 100.0

        def offset_func(name):
            def func(a):
                self.__dict__[name] += float(a) / 100.0
            return func

        def scale_func(name, ratio=0.01):
            def func(a):
                self.__dict__[name] *= 2 ** (float(a) * ratio)
            return func

        self.sliders = [
            Slider(20, 20, offset_func('color_offset'), 'offset'),
            Slider(20, 42, scale_func('color_scale'), 'contrast'),
            Slider(20, 64, scale_func('volume', ratio=0.05), 'volume'),
        ]

    def init(self, w, h):
        gl.glEnable(gl.GL_DEPTH_TEST)

        self.resize(w, h)

    def resize(self, w, h):
        self.screen_size = (w, h)

        gl.glViewport(0, 0, w, h)

        ratio = float(w) / float(h)
        self.projection = projection_matrix(60.0, ratio, 0.1, 100.0)
        self.projection_inv = np.linalg.inv(self.projection)

        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadMatrixf(self.projection.transpose())
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()

    def draw(self):
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        gl.glLoadIdentity()

        mat = np.dot(np.dot(np.dot(translation_matrix(0, 0, -3.0), self.modelview),
                            scale_matrix(2.0, 1.0, 0.3)), translation_matrix(-0.5, 2.5, -0.5))

        gl.glMultMatrixf(mat.transpose())
        gl.glColor3f(1.0, 1.0, 1.0)

        gl.glTranslatef(0, float(self.shift) / self.waterfall.history, 0)
        gl.glScalef(1.0, 5.0, 1.0)
        self.waterfall.draw_scroll(self.color_offset, self.color_scale)

        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gluOrtho2D(0.0, self.screen_size[0], 0.0, self.screen_size[1])
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

#        gl.glPushMatrix()
#        gl.glTranslatef(100, 100, 0)
#
#        gl.glColor4f(1.0, 1.0, 1.0, 1.0)
#
#        gl.glBegin(gl.GL_LINES)
#        gl.glVertex2i(10, 8)
#        gl.glVertex2i(0, 4)
#        gl.glVertex2i(10, 0)
#        gl.glVertex2i(0, 4)
#
#        gl.glVertex2i(35, 8)
#        gl.glVertex2i(45, 4)
#        gl.glVertex2i(35, 0)
#        gl.glVertex2i(45, 4)
#        gl.glEnd()
#
#        gl.glPopMatrix()

        for a in self.sliders:
            a.draw()

        gl.glDisable(gl.GL_BLEND)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_MODELVIEW)

    def event2world(self, event):
        v = screen2world(self.projection_inv,
                         float(event.motion.x) / self.screen_size[0] * 2.0 - 1.0,
                         float(event.motion.y) / self.screen_size[1] * 2.0 - 1.0)
        return np.dot(self.view_inv, np.concatenate((normv(v), np.array([1]))))[0:3]

    def event(self, event):
        if event.type == sdl2.SDL_MOUSEBUTTONDOWN \
                or event.type == sdl2.SDL_MOUSEBUTTONUP \
                or event.type == sdl2.SDL_MOUSEMOTION:
            event.motion.y = self.screen_size[1] - event.motion.y

        for a in self.sliders:
            if a.event(event):
                return True

        if event.type == sdl2.SDL_MOUSEBUTTONDOWN and (event.motion.state & sdl2.SDL_BUTTON_LEFT):
            self.drag_start = self.event2world(event)

        if event.type == sdl2.SDL_MOUSEMOTION and (event.motion.state & sdl2.SDL_BUTTON_LEFT):
            v = self.event2world(event)
            c = np.cross(self.drag_start, v)

            self.modelview = np.dot(self.view, rotation_matrix(normv(c), math.atan2(np.linalg.norm(c), np.vdot(self.drag_start, v))))

        if event.type == sdl2.SDL_MOUSEBUTTONUP and (event.motion.state & sdl2.SDL_BUTTON_LEFT):
            self.view = self.modelview
            self.view_inv = np.linalg.inv(self.view)

        if event.type == sdl2.SDL_WINDOWEVENT and event.window.event == sdl2.SDL_WINDOWEVENT_RESIZED:
            self.resize(event.window.data1, event.window.data2)

        if event.type == sdl2.SDL_USEREVENT:
            self.cb_idle()

    def cb_idle(self):
        try:
            rec = self.inserts.get(block=False)
            self.waterfall.insert(rec)
        except queue.Empty:
            return


class interp_fir_filter:
    def __init__(self, taps, interp):
        self.interp = interp
        self.nhistory = (len(taps) - 1) // interp
        padlen = (self.nhistory + 1) * interp - len(taps)
        self.taps = np.concatenate((np.zeros(padlen, dtype=taps.dtype), taps))

    def __call__(self, inp):
        interp = self.interp
        res = np.zeros((len(inp) - self.nhistory) * interp, dtype=inp.dtype)

        for i in range(interp):
            res[i::interp] = np.convolve(inp, self.taps[i::interp], mode='valid')

        return res


class freq_translator:
    def __init__(self, phase_inc):
        self.phase_inc = phase_inc
        self.phase = 1.0

    def __call__(self, inp):
        shift = np.exp(1j * self.phase_inc * np.arange(len(inp), dtype=np.float32)) * self.phase
        self.phase = shift[-1] * np.exp(1j * self.phase_inc)
        return inp * shift


def lowpass(w_c, N, start=None):
    a = np.arange(N) - (float(N - 1) / 2)
    taps = np.sin(a * w_c) / a / np.pi

    if N % 2 == 1:
        taps[N/2] = w_c / np.pi

    return taps


class RingBuf:
    def __init__(self, headlen, buf):
        self.headlen = headlen
        self.buf = buf
        self.fill_edge = -headlen

    def __len__(self):
        return len(self.buf) - self.headlen

    def append(self, stuff):
        stufflen = len(stuff)

        if self.fill_edge + stufflen + self.headlen > len(self.buf):
            self.buf[0:self.headlen] = self.buf[self.fill_edge:self.fill_edge + self.headlen]
            self.fill_edge = 0

        self.slice(self.fill_edge, self.fill_edge + stufflen)[:] = stuff
        self.fill_edge += stufflen

    def slice(self, a, b):
        return self.buf[a + self.headlen: b + self.headlen]


UPDATE_EVENT_TYPE = sdl2.SDL_RegisterEvents(1)
UPDATE_EVENT = sdl2.SDL_Event()
UPDATE_EVENT.type = UPDATE_EVENT_TYPE


def input_thread(readfunc, ringbuf, nbins, overlap, viewer):
    window = 0.5 * (1.0 - np.cos((2 * math.pi * np.arange(nbins)) / nbins))

    #ringbuf.append(np.fromfile(fil, count=ringbuf.headlen, dtype=np.complex64))
    ringbuf.append(np.frombuffer(readfunc(ringbuf.headlen * 8), dtype=np.complex64))

    while True:
        #ringbuf.append(np.fromfile(fil, count=nbins - overlap, dtype=np.complex64))
        ringbuf.append(np.frombuffer(readfunc((nbins - overlap) * 8), dtype=np.complex64))

        frame = ringbuf.slice(ringbuf.fill_edge - nbins, ringbuf.fill_edge)
        spectrum = np.absolute(np.fft.fft(np.multiply(frame, window)))
        spectrum = np.concatenate((spectrum[nbins//2:nbins], spectrum[0:nbins//2]))
        spectrum = np.log10(spectrum) * 10
        viewer.inserts.put(spectrum / 20.0)

        sdl2.SDL_PushEvent(UPDATE_EVENT)


def main():
    if len(sys.argv) != 2:
        print("usage: 3dwf.py REMOTE_ADDRESS", file=sys.stderr)
        sys.exit(1)

    nbins = 256
    overlap = 192
    rem_address = (sys.argv[1], 3731)

    conn = socket.create_connection(rem_address)

    sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_AUDIO)

    window = sdl2.SDL_CreateWindow(b"3D Waterfall", sdl2.SDL_WINDOWPOS_CENTERED,
                                   sdl2.SDL_WINDOWPOS_CENTERED, 800, 600,
                                   sdl2.SDL_WINDOW_RESIZABLE | sdl2.SDL_WINDOW_OPENGL)
    context = sdl2.SDL_GL_CreateContext(window)

    wf = WFViewer(nbins)
    wf.init(800, 600)
    wf.shift = 0

    filt = interp_fir_filter(lowpass(np.pi / 4, 512) * np.hamming(512), 4)
    freqx = freq_translator((0.8/8.0) * np.pi)

    headlen = max(filt.nhistory, overlap)
    ringbuf = RingBuf(headlen, np.zeros(headlen + (nbins - overlap) * 512, dtype=np.complex64))

    # FIXME
    global audio_edge
    audio_edge = 0

    def callback(unused, buf, buflen):
        global audio_edge
        bufbuf = pybuf_from_memory(buf, buflen, 0x200) # PyBUF_WRITE
        array = np.frombuffer(bufbuf, np.float32)

        assert len(array) % filt.interp == 0 # TODO
        nreqframes = len(array) // filt.interp

        loc_ringbuf_edge = ringbuf.fill_edge
        if loc_ringbuf_edge < 0 or (loc_ringbuf_edge - audio_edge) % len(ringbuf) < nreqframes:
            print("audio underrun", file=sys.stderr)
            array.fill(0)
            return

        # TODO
        if audio_edge + nreqframes > len(ringbuf):
            audio_edge = 0

        slic = ringbuf.slice(audio_edge - filt.nhistory, audio_edge + nreqframes)
        array[:] = np.real(freqx(filt(slic))) * wf.volume
        audio_edge += nreqframes
        sdl2.SDL_PushEvent(UPDATE_EVENT)

    audio_spec = sdl2.SDL_AudioSpec(8000,
                                    sdl2.AUDIO_F32,
                                    1,
                                    512,
                                    sdl2.SDL_AudioCallback(callback))
    audio_dev = sdl2.SDL_OpenAudioDevice(None, 0, audio_spec, None, 0)
    if audio_dev == 0:
        raise Error('could not open audio device')

    err_queue = queue.Queue()

    def readfunc(nbytes):
        bytes = b''

        while len(bytes) < nbytes:
            ret = conn.recv(nbytes - len(bytes))

            if not ret:
                raise Exception('end of stream')

            bytes += ret

        return bytes

    def thread_target():
        try:
            input_thread(readfunc, ringbuf, nbins, overlap, wf)
        except Exception as e:
            err_queue.put(e)
            event = sdl2.SDL_Event()
            event.type = sdl2.SDL_QUIT
            sdl2.SDL_PushEvent(event)

    other_thread = threading.Thread(target=thread_target)
    other_thread.setDaemon(True)
    other_thread.start()

    sdl2.SDL_PauseAudioDevice(audio_dev, 0)

    running = True
    event = sdl2.SDL_Event()
    while running:
        sdl2.SDL_WaitEvent(ctypes.byref(event))

        while True:
            if event.type == sdl2.SDL_QUIT:
                running = False
                break

            wf.event(event)

            if sdl2.SDL_PollEvent(ctypes.byref(event)) == 0:
                break

        # FIXME
        wf.shift = ((ringbuf.fill_edge - audio_edge) % len(ringbuf)) / (nbins - overlap)
        wf.draw()
        sdl2.SDL_GL_SwapWindow(window)

    try:
        for exc in iter(err_queue.get_nowait, None):
            sdl2.SDL_ShowSimpleMessageBox(sdl2.SDL_MESSAGEBOX_ERROR, b"Exception", str(exc).encode("ascii"), None)
    except queue.Empty:
        pass

    sdl2.SDL_CloseAudioDevice(audio_dev)
    sdl2.SDL_GL_DeleteContext(context)
    sdl2.SDL_DestroyWindow(window)
    sdl2.SDL_Quit()


if __name__ == "__main__":
    main()
