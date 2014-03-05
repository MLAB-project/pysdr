# Hardware accelerated SDR waterfall PySDR

![UST logo](http://www.ust.cz/include/Logo_UST.png "UST")

## What

Jack sink waterfall with OpenGL acceleration. This software plot live waterfall from jack source. This software is intendent to radioastronomy purposes.

## Supported designs

### RMDS01A-C
Radio Meteor detection stations. 

Technical description this station is accessible from:
http://wiki.mlab.cz/doku.php?id=en:rmds 

Station itself can be purchased from UST online store at: 
http://www.ust.cz/shop/product_info.php?products_id=223


## Dependencies 

* python
* python-opengl
* python-dev
* python-numpy
* libjack-dev

### Ubuntu 13.10

    $ sudo apt-get install python-numpy python-opengl python-dev libjack-jackd2-dev

## Howto

### Compiling

In the root directory of this repository:

    $ python setup.py build_ext --inplace

### Running

Start qjackctl, run jack daemon and then run pySDR:

    $ python waterfall.py


# Experimental record viewer

It can be used to view RAW data record from RMDS system. Recalculates the waterfall with different number of bins according to its visual stretching.


## License

Everything in this repository is GNU GPL v3 licensed.
