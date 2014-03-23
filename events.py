import traceback
import sys

from OpenGL.GL import *

from graph import *

class EventMarker:
    def __init__(self, viewer, mark_color=None):
        self.viewer = viewer
        self.mark_color = mark_color or (0.0, 1.0, 0.0, 1.0)
        self.marks = []

    def on_event(self, event_id, payload):
        if event_id.startswith('mlab.aabb_event.'):
            event_mark = (event_id, (payload[0], payload[1]), (payload[2], payload[3]), payload[4])

            for i in xrange(len(self.marks)):
                mark = self.marks[i]
                if (mark[0] == event_mark[0] and mark[1][0] == event_mark[1][0]
                        and event_mark[2] == event_mark[2]):
                    self.marks[i] = event_mark
                    return
            self.marks.append(event_mark)

    def draw_content(self):
        for (event_id, row_range, freq_range, desc) in self.marks:
            xa, xb = [self.viewer.bin_to_x(x) for x in freq_range]
            ya, yb = [self.viewer.row_to_y(x) for x in row_range]

            glLineWidth(2)
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            glColor4f(*self.mark_color)
            glBegin(GL_QUADS)
            glVertex2f(xa, ya)
            glVertex2f(xa, yb)
            glVertex2f(xb, yb)
            glVertex2f(xb, ya)
            glEnd()
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            glLineWidth(1)

            glColor4f(1.0, 1.0, 1.0, 1.0)
            self.viewer.overlay.draw_text(xb, ya, desc)

    def on_texture_insert(self):
        self.marks = [(a, b, c, d) for (a, b, c, d) in self.marks \
                      if b[1] > self.viewer.texture_row - self.viewer.multitexture.get_height()]

class TemporalPlot(PlotLine):
    def __init__(self, viewer, x_offset, title=None):
        PlotLine.__init__(self, 2 * viewer.multitexture.get_height())
        self.viewer = viewer
        self.x_offset = x_offset
        self.title = title
        self.data[:] = np.zeros(self.points)

    def draw_screen(self):
        view = self.viewer.view

        glPushMatrix()
        glTranslated(self.x_offset, view.origin_y, 0)
        glScalef(-10.0, view.scale_y, 1.0)

        glColor4f(0.0, 0.0, 0.0, 0.7)
        glBegin(GL_QUADS)
        glVertex2f(-5.0, 0.0)
        glVertex2f(5.0, 0.0)
        glVertex2f(5.0, 1.0)
        glVertex2f(-5.0, 1.0)
        glEnd()
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glRotatef(90, 0, 0, 1)
        glScalef(2, 1, 1)
        glTranslatef(0.5 / self.points, 0.0, 0.0)
        PlotLine.draw_section(self, self.viewer.texture_row - self.viewer.multitexture.get_height(),
                              self.viewer.texture_row - 1)
        glPopMatrix()

        if self.title:
            self.viewer.overlay.draw_text_ss(self.x_offset - 45, view.origin_y + view.scale_y + 5,
                                                self.title)

    def set(self, row, value):
        self.data[row % self.points] = value

class TemporalFreqPlot(TemporalPlot):
    def __init__(self, viewer, title):
        TemporalPlot.__init__(self, viewer, 0, title)

    def draw_screen(self):
        pass

    def draw_content(self):
        glColor4f(1.0, 1.0, 1.0, 1.0)

        glPushMatrix()
        glScalef(-1, 2, 1)
        glRotatef(90, 0, 0, 1)
        glTranslatef(0.5 / self.points, 0.0, 0.0)
        PlotLine.draw_section(self, self.viewer.texture_row - self.viewer.multitexture.get_height(),
                              self.viewer.texture_row - 1)
        glPopMatrix()

SCRIPT_API_METHODS = dict()

class DetectorScript:
    def script_api(func):
        SCRIPT_API_METHODS[func.func_name] = func

    @script_api
    def peak(self, a, b, s):
        bin = np.argmax(s[a:b])
        return (s[bin], bin + a)

    @script_api
    def noise(self, a):
        return np.sort(a)[len(a) / 4] * 2

    @script_api
    def plot(self, name, value):
        if not name in self.plots:
            self.plots[name] = TemporalPlot(self.viewer, self.plot_x_offset, name)
            self.plot_x_offset = self.plot_x_offset + 120

        self.plots[name].set(self.viewer.process_row, value)

    @script_api
    def plot_bin(self, name, value):
        if not name in self.plots:
            self.plots[name] = TemporalFreqPlot(self.viewer, name)

        self.plots[name].set(self.viewer.process_row, (float(value) / self.viewer.bins) * 2 - 1)

    @script_api
    def plot_freq(self, name, value):
        self.namespace['plot_bin'](name, self.viewer.freq_to_bin(value))

    @script_api
    def emit_event(self, event_id, payload):
        [l.on_event(event_id, payload) for l in self.listeners]

    def __init__(self, viewer, listeners, filename):
        self.viewer = viewer
        self.filename = filename
        self.plots = dict()
        self.plot_x_offset = 100
        self.disabled = False

        self.listeners = listeners

        self.namespace = {
            'freq2bin': self.viewer.freq_to_bin,
            'bin2freq': self.viewer.bin_to_freq,
            'row_duration': self.viewer.row_duration
        }

        for name, func in SCRIPT_API_METHODS.items():
            self.namespace[name] = func.__get__(self, DetectorScript)

        execfile(filename, self.namespace)

    def draw_screen(self):
        for plot in self.plots.values():
            if hasattr(plot.__class__, 'draw_screen'):
                plot.draw_screen()

    def draw_content(self):
        for plot in self.plots.values():
            if hasattr(plot.__class__, 'draw_content'):
                plot.draw_content()

    def on_lin_spectrum(self, spectrum):
        if self.disabled:
            return

        try:
            self.namespace['run'](self.viewer.process_row, spectrum)
        except Exception:
            print "exception in %s, disabling:" % self.filename
            traceback.print_exc(file=sys.stdout)
            self.disabled = True

class MIDIEventGatherer:
    def __init__(self, viewer, listeners):
        self.viewer = viewer
        self.listeners = listeners

    def on_log_spectrum(self, spectrum):
        for frame, message in self.viewer.sig_input.get_midi_events():
            if len(message) > 3 and message[0:2] == "\xf0\x7d" and message[-1] == "\xf7":
                try:
                    event_id, payload = message[2:-1].split(':', 1)
                    payload = tuple(payload.split(','))

                    if event_id.startswith('mlab.aabb_event.'):
                        rel_frame_a, rel_frame_b, freq_a, freq_b, desc = payload

                        row_range = tuple([(frame + int(x)) / (self.viewer.bins - self.viewer.overlap)
                                           for x in (rel_frame_a, rel_frame_b)])
                        bin_range = tuple([self.viewer.freq_to_bin(float(x)) for x in (freq_a, freq_b)])

                        payload = row_range + bin_range + (desc,)

                    [l.on_event(event_id, payload) for l in self.listeners]
                except (ValueError, TypeError) as e:
                    print "failed to parse MIDI message '%s': %s" % (message[2:-1], e)
            else:
                print "unknown MIDI message at frame %d: %s" % (frame, message.encode("hex"))
