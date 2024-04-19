import numpy as np
import time
import sys

import pysdr.ext as ext

class SigInput:
    def __init__(self):
        self.sample_rate = 0
        self.no_channels = 0

    def read(self, frames):
        raise NotImplementedError("read() method must be overrided")

    def start(self):
        raise NotImplementedError("start() method must be overrided")

class RawSigInput(SigInput):
    def __init__(self, sample_rate, no_channels, dtype, file):
        self.sample_rate = sample_rate
        self.no_channels = no_channels
        self.dtype = dtype
        self.file = file

    def read(self, frames):
        read_len = frames * self.dtype.itemsize * self.no_channels
        buffer = b''

        while len(buffer) < read_len:
            buffer += self.file.read(read_len - len(buffer))

        if self.no_channels == 1:
            return np.frombuffer(buffer, dtype=self.dtype).astype(np.float32)
        elif self.no_channels == 2 and self.dtype == np.dtype(np.float32):
            return np.frombuffer(buffer, dtype=np.complex64)
        else:
            raise NotImplementedError("unimplemented no of channels and type combination")

    def start(self):
        pass

    def __str__(self):
        return "raw input from '%s'" % self.file.name

class JackInput(SigInput):
    def __init__(self, name):
        self.name = name
        self.handle = ext.jack_init(name)
        self.sample_rate = ext.jack_get_sample_rate(self.handle)

    def read(self, frames):
        while True:
            r = ext.jack_gather_samples(self.handle, frames)

            if r != None:
                return r

            time.sleep(float(frames) / self.sample_rate / 10)

    def get_midi_events(self):
        events = []

        while True:
            event = ext.jack_gather_midi_event(self.handle)

            if event == None:
                break
            
            events.append(event)

        return events

    def start(self):
        ext.jack_activate(self.handle)

    def __str__(self):
        return "JACK port '%s'" % self.name
