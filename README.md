# Hardware accelerated SDR waterfall

![UST logo](http://www.ust.cz/include/Logo_UST.png "UST")

## What

Jack sink waterfall with OpenGL acceleration. This software plot live waterfall from jack source. This software is intendent to radioastronomy purposes.

## Supported designs
###[RMDS01A](http://www.ust.cz/shop/product_info.php?cPath=38&products_id=223)


## Dependencies 

Python
python-opengl

### Ubuntu 13.04

 sudo apt-get install python-numpy python-opengl python-dev libjack-jackd2-dev


## Howto

### Compiling

1. cd to project in pysdrext/ directory

2. python setup.py

3. perform option 3. (pres enter two times) 

4. python ../waterfall.py

### Running

Start qjackctl, run jack daemon and then run pySDR:

python waterfall.py

## License

Everything in this repository is GNU GPL v3 licensed.
