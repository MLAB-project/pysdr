import numpy as np

iter_time = float(freq2bin(1000) - freq2bin(0)) / 1000
avg_spread_bin = freq2bin(100) - freq2bin(0)

state = None
last_detect_row = None

def run(row, spectrum):
	global state, last_detect_row

	(peak_pow, peak_bin) = peak(freq2bin(10300), freq2bin(10900), spectrum)
	avg_pow = np.average(spectrum[peak_bin - avg_spread_bin:peak_bin + avg_spread_bin])
	noise_pow = noise(spectrum[freq2bin(9000):freq2bin(9600)])

	print "noise_pow: %f avg_pow: %f sn: %f" % (noise_pow, avg_pow, avg_pow - noise_pow)

	if avg_pow - noise_pow > 0.1:
		last_detect_row = row
		if state == None:
			print "METEOR"
			mark(row, peak_bin, "METEOR")
			state = ("METEOR", peak_bin)
	elif state != None and (row - last_detect_row) * iter_time > 1.6:
		print "END"
		mark(row, state[1], "END")
		state = None
