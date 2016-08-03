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
        string = ""

        while len(string) < read_len:
            string += self.file.read(read_len - len(string))

        if self.no_channels == 1:
            return np.fromstring(string, dtype=self.dtype).astype(np.float32)
        elif self.no_channels == 2 and self.dtype == np.dtype(np.float32):
            return np.fromstring(string, dtype=np.complex64)
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


import zmq
import struct
import StringIO

def pmt_unpack_sym(inp):
    length, = struct.unpack(">H", inp.read(2))

    return inp.read(length)

def pmt_unpack(inp):
    tag, = struct.unpack("<B", inp.read(1))

    return {
        0x00: lambda a: True,
        0x01: lambda a: False,
        0x02: pmt_unpack_sym,
        0x03: lambda i: struct.unpack(">i", i.read(4))[0],
        0x04: lambda i: struct.unpack(">d", i.read(8))[0],
        0x0b: lambda i: struct.unpack(">Q", i.read(8))[0],
        0x0c: lambda i: tuple([pmt_unpack(i) for _ in xrange(struct.unpack(">I", i.read(4))[0])]),
    }[tag](inp)

class ZMQInput(SigInput):
    def __init__(self, addr, rate):
        self.addr = addr
        self.sample_rate = rate
        self.buf = np.zeros(0, dtype=np.complex64)
        self.events = []
        self.tag_offset = None
        self.nframes_received = 0

    def recv(self):
        msg = self.sock.recv()

        hdr_magic, hdr_version, \
            offset_out, rcv_ntags = struct.unpack("=HBQQ", msg[0:19])

        if hdr_magic != 0x5ff0 or hdr_version != 0x01:
            print "pysdr: invalid magic or version \
                   in ZMQ message header, dropping"
            return

        msg_reader = StringIO.StringIO(msg[19:])

        for _ in xrange(rcv_ntags):
            offset = struct.unpack("=Q", msg_reader.read(8))[0] \
                     - offset_out + self.nframes_received
            key = pmt_unpack(msg_reader)
            value = pmt_unpack(msg_reader)
            srcid = pmt_unpack(msg_reader)
            self.events.append((offset, key, value))

        #print len(msg_reader.read())

        ret = np.fromstring(msg_reader.read(), dtype=np.complex64)
        self.nframes_received += len(ret)
        return ret

    def get_events(self):
        ret = self.events
        self.events = []
        return ret

    def read(self, nframes):
        frames = ret_frames = np.zeros(nframes, dtype=np.complex64)

        while len(frames) > 0:
            if len(self.buf) == 0:
                self.buf = self.recv()

            copylen = min(len(self.buf), len(frames))
            frames[0:copylen] = self.buf[0:copylen]
            frames, self.buf = frames[copylen:], self.buf[copylen:]

        return ret_frames

    def start(self):
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.SUB)
        self.sock.connect(self.addr)
        self.sock.setsockopt(zmq.SUBSCRIBE, "")

    def __str__(self):
        return "ZMQ subscription, '%s'" % self.addr
