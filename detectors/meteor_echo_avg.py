import numpy as np

avg_spread_bin = freq2bin(100) - freq2bin(0)
timeout_nrows = int(1.6 / row_duration)

ongoing_event = False
last_detect_row = None
meteor_treshold = 0.7

def run(row, spectrum):
    global ongoing_event, last_detect_row

    (peak_pow, peak_bin) = peak(freq2bin(26400), freq2bin(26600), spectrum)
    avg_pow = np.average(spectrum[freq2bin(26450):freq2bin(26550)])
    noise_pow = np.average(spectrum[freq2bin(25000):freq2bin(26000)])

    sn = np.log(avg_pow / (noise_pow))
    plot("sn", sn)

    if sn > meteor_treshold:
        last_detect_row = row
        if not ongoing_event:
            ongoing_event = (row - int(0.5 / row_duration), row + timeout_nrows,
                             peak_bin - avg_spread_bin, peak_bin + avg_spread_bin,
                             "@ %.3f kHz" % (bin2freq(peak_bin) / 1000))
        ongoing_event = (ongoing_event[0], row + timeout_nrows) + ongoing_event[2:5]

        emit_event("mlab.aabb_event.meteor_echo", ongoing_event)
    elif ongoing_event and (row - last_detect_row) > timeout_nrows:
        ongoing_event = None
