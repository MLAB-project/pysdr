# PySDR

SDR utilities written in Python

![UST logo](http://www.ust.cz/include/Logo_UST.png "UST")

## Waterfall

Plots live spectral waterfall of a quadrature signal which can be taken either from the JACK audio system or the standard input. The graphical work is offloaded to GPU via OpenGL.

	$ pysdr-waterfall -h
	usage: pysdr-waterfall [-h] [-b BINS] [-H HEIGHT] [-o OVERLAP] [-j NAME]
	                       [-r RATE] [-d FILENAME] [-p CONFIG_FILE]
	
	Plot live spectral waterfall of a quadrature signal.
	
	optional arguments:
	  -h, --help            show this help message and exit
	  -b BINS, --bins BINS  number of FFT bins (default: 4096)
	  -H HEIGHT, --height HEIGHT
	                        minimal height of the waterfall in seconds (default
	                        1024 FFT rows)
	  -o OVERLAP, --overlap OVERLAP
	                        overlap between consecutive windows as a proportion of
	                        the number of bins (default: 0.75)
	  -j NAME, --jack NAME  feed signal from JACK and use the given client name
	                        (by default, with name 'pysdr')
	  -r RATE, --raw RATE   feed signal from the standard input, 2 channel
	                        interleaved floats with the given samplerate
	  -d FILENAME, --detector FILENAME
	                        attach the given detector script
      -p CONFIG_FILE,       configuration file to which the waterfall display configuration is saved. 
                            Configuration stored in file is updated by pressing of "p" key. 
### Example usage with ALSA

	$ arecord -f FLOAT_LE -c 2 -r 44100 --buffer-size 1024 | pysdr-waterfall -r 44100

## Record Viewer

Shows spectral waterfall of short raw recordings stored in WAV files or FITS files produced by [Radio Observer](https://github.com/MLAB-project/radio-observer). Recalculates the waterfall with different number of bins according to its visual stretching.

### Usage

	$ pysdr-recviewer path/to/recording

## Dependencies

### Ubuntu 13.10

    $ sudo apt-get install python-numpy python-opengl python-dev libjack-jackd2-dev

## Inplace build

	$ python setup.py build_ext --inplace

## Installation

	$ python setup.py install

## Supported designs

### Radio Meteor Detection Station

PySDR is developed to be used, among others, with the Radio Meteor Detection Station designs.

[Technical description](http://wiki.mlab.cz/doku.php?id=en:rmds)

[Purchase from UST](http://www.ust.cz/shop/product_info.php?products_id=223)

## License

Everything in this repository is GNU GPL v3 licensed.
