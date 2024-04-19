import numpy as np
import time
import math
from pymlab import config

def reduce(a, div=4, start=1, stop=3):
    return np.sum(np.sort(a, axis=0)[len(a)*start/div:len(a)*stop/div], axis=0) / (len(a) / 2)

def coroutine():
    def sleep(time):
        for i in range(int(math.ceil(float(time) / row_duration))):
            yield

    if len(args) != 5:
        raise Exception("usage: pysdr-waterfall [OTHER_PYSDR_ARGS] -d 'detectors/noise_level.py I2C_CONFIG_FILENAME OUTPUT_FILENAME START_HZ STOP_HZ STEP_HZ'")

    cfg = config.Config()
    cfg.load_python(args[0])
    cfg.initialize()
    fgen = cfg.get_device('clkgen')
    fgen.reset()

    for i in sleep(3.0):
        yield

    fgen = cfg.get_device('clkgen')
    fgen.recall_nvm()

    for i in sleep(2.0):
        yield

    freqs = range(int(args[2]), int(args[3]), int(args[4]))

    nmeas_rows = int(math.ceil(float(1.0) / row_duration))
    arr = np.zeros(nmeas_rows, dtype=np.float32)

    with file(args[1], 'w') as outfile:
        for freq in freqs:
            fgen.recall_nvm()
            print("resetting")
            for i in sleep(0.2):
                yield

            freq_mhz = float(freq) / 1000000
            fgen.set_freq(10., freq_mhz * 2)
            print("setting freq %f" % freq_mhz)
            for i in sleep(1.0):
                yield

            row, _s, _n = yield

            emit_event("mlab.aabb_event.measurement_area", (row, row + nmeas_rows, 0, 4096, "%f MHz" % (freq_mhz,)))

            for i in range(nmeas_rows):
                _r, _s, noise_lvl = yield
                arr[i] = noise_lvl

            noise_lvl_sum = reduce(arr)

            print("for freq %f, noise level is %f" % (freq_mhz, noise_lvl_sum))
            outfile.write("\t%f\t%f\n" % (freq_mhz, noise_lvl_sum))
            outfile.flush()

coroutine_inst = None

def log_spectrum_pass(row, spectrum):
    global coroutine_inst

    if coroutine_inst is None:
        coroutine_inst = coroutine()
        coroutine_inst.send(None)

    noise_lvl = reduce(spectrum)
    plot("noise", noise_lvl / 5.0)
    try:
        coroutine_inst.send((row, spectrum, noise_lvl))
    except StopIteration:
        if __name__ == "__main__":
            sys.exit(0)

def process(sig_input, nbins, overlap):
    window = 0.5 * (1.0 - np.cos((2 * math.pi * np.arange(nbins)) / nbins))

    process_row = 0
    ringbuf = np.zeros(nbins * 4, dtype=np.complex64)
    ringbuf_edge = nbins
    readsize = nbins - overlap

    while True:
        if (ringbuf_edge + readsize > len(ringbuf)):
            ringbuf[0:overlap] = ringbuf[ringbuf_edge - overlap:ringbuf_edge]
            ringbuf_edge = overlap

        ringbuf[ringbuf_edge:ringbuf_edge + readsize] = sig_input.read(readsize)
        ringbuf_edge += readsize

        signal = ringbuf[ringbuf_edge - nbins:ringbuf_edge]

        spectrum = np.absolute(np.fft.fft(np.multiply(signal, window)))
        spectrum = np.concatenate((spectrum[nbins/2:nbins], spectrum[0:nbins/2]))

        log_spectrum_pass(process_row, np.log10(spectrum) * 20)
        process_row = process_row + 1

class RawSigInput:
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

if __name__ == "__main__":
    global row_duration, plot, emit_event, args
    import sys

    args = sys.argv[1:]
    plot = lambda a, b: None
    emit_event = lambda a, b: None
    nbins = 4096
    overlap = 3072
    sig_input = RawSigInput(48000, 2, np.dtype(np.float32), sys.stdin)
    row_duration = float(nbins - overlap) / sig_input.sample_rate
    process(sig_input, 4096, 3072)
