import numpy as np
import math
import time

from OpenGL.GL import *
from OpenGL.GL.ARB.framebuffer_object import *
from OpenGL.GL.EXT.framebuffer_object import *

from pysdr.overlay import View
from pysdr.persistance import pers_save

class KeyTriggers:
    def __init__(self, cmds):
        self.cmds = cmds

    def on_key_press(self, key):
        try:
            cmd = self.cmds[key]
        except KeyError:
            return False

        cmd[0](*(cmd[1]))
        return True

def screenshot(viewer):
    try:
        from PIL import Image

        resolution = viewer.screen_size

        image = np.zeros((resolution[1], resolution[0], 3), dtype=np.uint8)
        glReadPixels(0, 0, resolution[0], resolution[1], GL_RGB, GL_UNSIGNED_BYTE, image)

        Image.fromarray(image[::-1,:,:].copy()).save(time.strftime("screenshot_%Y%m%d%H%M%S.bmp",
                                                                   time.gmtime()))
    except Exception as e:
        print e

def textureshot(viewer):
    prev_view = viewer.view
    prev_screen_size = viewer.screen_size

    try:
        from PIL import Image

        resolution = (viewer.multitexture.get_width(), viewer.multitexture.get_height())
        tile_size = (viewer.multitexture.unit_width, viewer.multitexture.unit_height)

        rbo = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, rbo)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_RGB8, tile_size[0], tile_size[1])

        fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, fbo)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, rbo)
        glFramebufferRenderbuffer(GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, rbo)

        viewer.cb_reshape(tile_size[0], tile_size[1])
        viewer.screen_size = resolution

        image = np.zeros((resolution[1], resolution[0], 3), dtype=np.uint8)
        tile_image = np.zeros((tile_size[1], tile_size[0], 3), dtype=np.uint8)

        viewer.view = view = View()
        view.scale_x, viewer.view.scale_y = float(resolution[0]) / 2, float(resolution[1])
        view.origin_x = resolution[0] / 2

        for x in xrange(viewer.multitexture.units_x):
            for y in xrange(viewer.multitexture.units_y):
                glClear(GL_COLOR_BUFFER_BIT)
                glClearColor(0, 0, 0, 1)
                glLoadIdentity()

                glMatrixMode(GL_PROJECTION)
                glPushMatrix()
                view.screen_offset = (-tile_size[0] * x, -tile_size[1] * y)
                glTranslatef(view.screen_offset[0], view.screen_offset[1], 0)
                glMatrixMode(GL_MODELVIEW)

                glPushMatrix()
                view.setup()
                viewer.call_layers('draw_content')
                glPopMatrix()

                glMatrixMode(GL_PROJECTION)
                glPopMatrix()
                glMatrixMode(GL_MODELVIEW)

                glReadPixels(0, 0, tile_size[0], tile_size[1], GL_RGB,
                             GL_UNSIGNED_BYTE, tile_image)
                image[tile_size[1] * y:tile_size[1] * (y + 1),
                      tile_size[0] * x:tile_size[0] * (x + 1)] = tile_image

        glDeleteFramebuffers(1, [fbo])
        glDeleteRenderbuffers(1, [rbo])

        Image.fromarray(image[::-1,:,:].copy()).save(time.strftime("textureshot_%Y%m%d%H%M%S.bmp",
                                                                   time.gmtime()))

    except Exception as e:
        print e

    viewer.view = prev_view
    viewer.cb_reshape(prev_screen_size[0], prev_screen_size[1])

def mag_range_calibration(viewer):
    class Hook:
        def on_log_spectrum(self, spectrum):
            a = int(((-viewer.view.origin_x) / viewer.view.scale_x + 1)
                    / 2 * viewer.bins)
            b = int(((-viewer.view.origin_x + viewer.screen_size[0]) / viewer.view.scale_x + 1)
                    / 2 * viewer.bins)

            a = max(0, min(viewer.bins - 1, a))
            b = max(0, min(viewer.bins - 1, b))

            if a != b:
                area = spectrum[a:b]
                mag_range = (np.min(area) + 0.5, np.max(area) + 1.0)

                if [math.isnan(a) or math.isinf(a) for a in mag_range] == [False, False]:
                    viewer.mag_range = mag_range

            viewer.layers.remove(self)

    viewer.layers.append(Hook())

def align_pixels(viewer):
    viewer.view.set_scale(viewer.multitexture.get_width(), viewer.multitexture.get_height(),
                          viewer.screen_size[0] / 2, viewer.screen_size[1] / 2)

def make_commands_layer(viewer):
    return KeyTriggers({
        's': (screenshot, (viewer,)),
        't': (textureshot, (viewer,)),
        'c': (mag_range_calibration, (viewer,)),
        'm': (align_pixels, (viewer,)),
        'p': (lambda v: pers_save(v, v.persfn), (viewer,))
    })
