def configuration(parent_package='',top_path=None):
    from numpy.distutils.misc_util import Configuration
    config = Configuration('pysdr', parent_package, top_path)
    config.add_extension('ext', ['ext.c'],
                         libraries=['jack', 'm'], include_dirs=['whistle'])
    return config
