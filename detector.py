import numpy as np

avg_spread_bin = freq2bin(100) - freq2bin(0)
timeout_nrows = int(1.6 / row_duration)

echo_ongoing = False
last_detect_row = None
meteor_treshold = 0.7

def run(row, spectrum):
	global echo_ongoing, last_detect_row

	(peak_pow, peak_bin) = peak(freq2bin(10300), freq2bin(10900), spectrum)
	avg_pow = np.average(spectrum[peak_bin - avg_spread_bin:peak_bin + avg_spread_bin])
	noise_pow = noise(spectrum[freq2bin(9000):freq2bin(9600)])

	sn = np.log(avg_pow / noise_pow)
	plot("sn", sn)

	if sn > meteor_treshold:
		last_detect_row = row
		cut(row + timeout_nrows)
		if not echo_ongoing:
			event((row - int(0.5 / row_duration), row + timeout_nrows),
					(peak_bin - avg_spread_bin, peak_bin + avg_spread_bin),
					"@ %.3f kHz" % (bin2freq(peak_bin) / 1000))
			echo_ongoing = True
	elif echo_ongoing and (row - last_detect_row) > timeout_nrows:
		final()
		echo_ongoing = False
