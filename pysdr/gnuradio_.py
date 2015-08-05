import numpy as np
from gnuradio import gr, blocks
import wx, wx.glcanvas
from waterfall import WaterfallWindow, RangeSelector
from commands import make_commands_layer
import OpenGL.GL as gl
from OpenGL.GLUT import GLUT_DOWN, GLUT_UP, GLUT_LEFT_BUTTON, GLUT_RIGHT_BUTTON
import threading
from types import MethodType

from wx import SystemSettings

try:
    import Queue as queue
except ImportError:
    import queue

import gnuradio.wxgui.plotter.gltext as gltext


def _viewer_draw_string(self, x, y, string):
    if 'gltext_cache' not in self.__dict__:
        self.gltext_cache = dict()

    gltext_cache = self.gltext_cache

    if string not in gltext_cache:
        font = SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font.SetPointSize(9)
        gltext_cache[string] = gltext.TextElement(string, font=font, foreground=wx.WHITE)

    gl.glPushMatrix()
    gl.glScalef(1, -1, 1)
    gltext_cache[string].draw_text(wx.Point(x, -y - 12))
    gl.glPopMatrix()
    gl.glEnable(gl.GL_BLEND)


class Canvas(wx.glcanvas.GLCanvas):
    def __init__(self, parent, sig_input):
        self.sig_input = sig_input
        attribList = (wx.glcanvas.WX_GL_DOUBLEBUFFER, wx.glcanvas.WX_GL_RGBA)

        wx.glcanvas.GLCanvas.__init__(self, parent, wx.ID_ANY, attribList=attribList)
        size=(800, 400)
        #self.SetSize(wx.Size(*size))
        self.SetSizeHints(*size)
        self.glctx = wx.glcanvas.GLContext(self)

        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_CHAR, self.on_keyboard)
        self.Bind(wx.EVT_MOTION, self.on_mouse)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_mouse_btn)
        self.Bind(wx.EVT_LEFT_UP, self.on_mouse_btn)
        self.Bind(wx.EVT_RIGHT_DOWN, self.on_mouse_btn)
        self.Bind(wx.EVT_RIGHT_UP, self.on_mouse_btn)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.SetFocus()

        self.resized = False
        self.viewer = None
        self.paint_scheduled = False

    def on_mouse(self, event):
        if self.viewer is None:
            return

        self.viewer.cb_motion(event.GetX(), event.GetY())
        self.update()

    def on_mouse_btn(self, event):
        if self.viewer is None:
            return

        self.viewer.cb_mouse(GLUT_LEFT_BUTTON if event.LeftDown() or event.LeftUp() else GLUT_RIGHT_BUTTON,
                             GLUT_DOWN if event.ButtonDown() else GLUT_UP,
                             event.GetX(), event.GetY())

    def on_keyboard(self, event):
        print chr(event.GetKeyCode())
        self.viewer.cb_keyboard(chr(event.GetKeyCode()), 0, 0)

    def on_size(self, event):
        self.resized = True

    def update(self):
        if not self.paint_scheduled:
            self.paint_scheduled = True
            wx.PostEvent(self, wx.PaintEvent())

    def on_paint(self, event):
        if not self.IsShownOnScreen():
            return

        self.SetCurrent(self.glctx)

        self.paint_scheduled = False

        if self.viewer is None:
            self.viewer = WaterfallWindow(self.sig_input, 4096, 1024, skip_glut=True,
                                            swap_buffers=self.SwapBuffers,
                                            post_redisplay=self.update)
            self.viewer.layers += [make_commands_layer(self.viewer), RangeSelector(self.viewer)]
            self.viewer.draw_string = MethodType(_viewer_draw_string, self.viewer, WaterfallWindow)
            self.viewer.start()
            self.resized = True

        if self.resized:
            self.viewer.cb_reshape(*self.GetSize())
            self.resized = False

        self.viewer.cb_idle(call_post_redisplay=False, no_timeout=True)
        self.viewer.cb_display()


class GNURadioInput(gr.sync_block):
    def __init__(self, readsize, sample_rate):
        gr.sync_block.__init__(
            self,
            name = "pysdr_gr_input",
            in_sig = [[('f', np.complex64, (readsize))]],
            out_sig = []
        )

        self.queue = queue.Queue()
        self.readsize = readsize
        self.sample_rate = sample_rate
        self.canvas = None

    def work(self, input_items, output_items):
        for a in input_items[0]:
            self.queue.put(np.copy(a['f']))

        if self.canvas is not None and self.canvas.viewer is not None:
            self.canvas.update()

        return len(input_items[0])

    def read(self, frames):
        if frames != self.readsize:
            raise Exception("GNURadioInput doesn't work that way")

        return self.queue.get()

    def start(self):
        pass

class waterfall(gr.hier_block2):
    def __init__(self, parent, cmd_args=None):
        readsize = 4096-1024

        gr.hier_block2.__init__(self, "waterfall",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex),
                                gr.io_signature(0, 0, 0))

        self.s2p = blocks.stream_to_vector(gr.sizeof_gr_complex, readsize)
        self.sink = GNURadioInput(readsize, 48000)
        self.connect(self, self.s2p, self.sink)
        self.win = Canvas(parent, self.sink)
        self.sink.canvas = self.win
