from OpenGL.GL import *

from graph import *

class TemporalPlot(PlotLine):
    def __init__(self, viewer, x_offset, title=None):
        PlotLine.__init__(self, viewer.multitexture.get_height())
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
        PlotLine.draw_scroll(self, self.viewer.texture_edge)
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
        glScalef(-1, 1, 1)
        glRotatef(90, 0, 0, 1)
        PlotLine.draw_scroll(self, self.viewer.texture_edge)
        glPopMatrix()

class DetectorScript():
    @staticmethod
    def peak(a, b, s):
        return (np.max(s[a:b]), np.argmax(s[a:b]) + a)

    @staticmethod
    def noise(a):
        return np.sort(a)[len(a)/4] * 2

    def cut(self, row):
        if self.event_marker.wip_mark == None:
            return

        (row_range, a, b) = self.event_marker.wip_mark
        self.event_marker.wip_mark = ((row_range[0], row), a, b)

    def plot(self, name, value):
        if not name in self.plots:
            self.plots[name] = TemporalPlot(self.viewer, self.plot_x_offset, name)
            self.plot_x_offset = self.plot_x_offset + 120

        self.plots[name].set(self.viewer.process_row, value)

    def plot_bin(self, name, value):
        if not name in self.plots:
            self.plots[name] = TemporalFreqPlot(self.viewer, name)

        self.plots[name].set(self.viewer.process_row, (float(value) / self.viewer.bins) * 2 - 1)

    def __init__(self, viewer, event_marker, file):
        self.viewer = viewer
        self.event_marker = event_marker
        self.plots = dict()
        self.plot_x_offset = 100

        self.__dict__['freq2bin'] = lambda x: int(x * viewer.bins / viewer.sig_input.sample_rate + viewer.bins / 2)
        self.__dict__['bin2freq'] = lambda x: float(x - viewer.bins / 2) / viewer.bins * viewer.sig_input.sample_rate
        self.__dict__['row_duration'] = float(viewer.bins - viewer.overlap) / viewer.sig_input.sample_rate

        self.__dict__['final'] = event_marker.final
        self.__dict__['event'] = event_marker.mark
        self.__dict__['cut'] = self.cut

        self.__dict__['plot'] = self.plot
        self.__dict__['plot_bin'] = self.plot_bin
        self.__dict__['plot_freq'] = lambda name, x: self.plot_bin(name, \
                                                                    self.__dict__['freq2bin'](x))

        self.__dict__['noise'] = self.noise
        self.__dict__['peak'] = self.peak

        execfile(file, self.__dict__)

    def draw_screen(self):
        for plot in self.plots.values():
            if hasattr(plot.__class__, 'draw_screen'):
                plot.draw_screen()

    def draw_content(self):
        for plot in self.plots.values():
            if hasattr(plot.__class__, 'draw_content'):
                plot.draw_content()

    def on_lin_spectrum(self, spectrum):
        self.run(self.viewer.process_row, spectrum)

class EventMarker():
    def __init__(self, viewer):
        self.viewer = viewer
        self.marks = []
        self.wip_mark = None

    def mark(self, row_range, freq_range, description):
        self.wip_mark = (row_range, freq_range, description)

    def final(self):
        if self.wip_mark == None:
            return

        self.marks.append(self.wip_mark)
        self.wip_mark = None

    def draw_content(self):
        for (row_range, freq_range, description) in self.marks \
                                                    + ([self.wip_mark] if self.wip_mark else []):
            xa, xb = [self.viewer.bin_to_x(x) for x in freq_range]
            ya, yb = [self.viewer.row_to_y(x) for x in row_range]
            
            glLineWidth(2)
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            glColor4f(0.0, 1.0, 0.0, 1.0)
            glBegin(GL_QUADS)
            glVertex2f(xa, ya)
            glVertex2f(xa, yb)
            glVertex2f(xb, yb)
            glVertex2f(xb, ya)
            glEnd()
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            glLineWidth(1)

            glColor4f(1.0, 1.0, 1.0, 1.0)
            self.viewer.overlay.draw_text(xb, ya, description)

    def on_texture_insert(self):
        self.marks = [(a, b, c) for (a, b, c) in self.marks \
                        if a[1] > self.viewer.texture_row - self.viewer.multitexture.get_height()]
