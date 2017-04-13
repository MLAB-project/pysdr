# PySDR

PySDR displays spectral waterfall, a visualization of signal's frequency spectrum over time. It is developed for SDR-related applications, but can be fed any equidistantly-sampled complex-valued signal for which it makes sense.

A live waterfall is launched by `pysdr-waterfall`. It connects to the JACK audio system and takes its input from there, or, if the flag `-r` is passed, it expects its input on the standard input in the form of an endless stream of 32-bit interleaved floats.

	$ pysdr-waterfall -h
	usage: pysdr-waterfall [-h] [-b BINS] [-H HEIGHT] [-o OVERLAP] [-j NAME]
	                       [-r RATE] [-d ARGS] [-p FILENAME]
	
	Plot live spectral waterfall of a quadrature signal.
	
	optional arguments:
	  -h, --help            show this help message and exit
	  -b BINS, --bins BINS  number of FFT bins (default: 4096)
	  -H HEIGHT, --height HEIGHT
	                        minimal height of the waterfall in seconds
	                        (default corresponds to 1024 windows)
	  -o OVERLAP, --overlap OVERLAP
	                        overlap between consecutive windows as a
	                        proportion of the number of bins (default: 0.75)
	  -j NAME, --jack NAME  feed signal from JACK and use the given client
	                        name (by default, with name 'pysdr')
	  -r RATE, --raw RATE   feed signal from the standard input, expects 2
	                        channel interleaved floats with the given sample-
	                        rate
	  -d ARGS, --detector ARGS
	                        attach the given detector script, expects to be
	                        given the script filename followed by arguments
	                        for the script, all joined by spaces and passed on
	                        the command-line as one quoted argument
	  -p FILENAME, --persfn FILENAME
	                        a file in which to preserve the visualization
	                        parameters that come from interactive
	                        manipulation, i.e. the visible area of the
	                        waterfall and the selected magnitude range (save
	                        triggered by pressing 'p')

![stretching](https://cloud.githubusercontent.com/assets/382160/24999343/6fe18d4e-203d-11e7-9c5e-1949dc2f508b.gif)

### Example usage with sox (cross-platform)

	$ sox -d -e floating-point -b 32 -r 48000 -t raw --buffer 1024 - | ./pysdr-waterfall -r 48000

### Example usage with ALSA

	$ arecord -f FLOAT_LE -c 2 -r 44100 --buffer-size 1024 | pysdr-waterfall -r 44100

## Record Viewer

There's also `pysdr-reciewer`, which displays spectral waterfall of short recordings. The recordings are expected to be either WAV files, or FITS files in the format produced by [Radio Observer](https://github.com/MLAB-project/radio-observer). The number of frequency bins reflects the aspect ratio of the waterfall, and so is interactive.

### Usage

	$ pysdr-recviewer path/to/recording

## Dependencies

### Ubuntu 13.10

    $ sudo apt-get install python-numpy python-opengl python-dev libjack-jackd2-dev

## In-place build

The package has a binary component which has to be built on the target machine. (It is not needed for `pysdr-waterfall` at the moment.)

For usage without installation, do an in-place build first.

	$ python setup.py build_ext --inplace

## Installation

	$ python setup.py install

## Supported designs

### Radio Meteor Detection Station

PySDR is developed to be used, among others, with the RMDS designs by the MLAB project.

[Technical description](http://wiki.mlab.cz/doku.php?id=en:rmds)

[Purchase from UST](http://www.ust.cz/shop/product_info.php?products_id=223)

## License

Everything in this repository is GNU GPL v3 licensed.
