def configuration(parent_package='', top_path=None):
    import numpy
    from numpy.distutils.misc_util import Configuration

    config = Configuration('.',
                           parent_package,
                           top_path)
    config.add_extension('ext', ['pysdrext/pysdr.c'], libraries=['jack'])

    return config

if __name__ == "__main__":
    from numpy.distutils.core import setup
    setup(configuration=configuration)
