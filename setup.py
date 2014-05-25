def configuration(parent_package='', top_path=None):
    from numpy.distutils.misc_util import Configuration

    config = Configuration(None, parent_package, top_path)
    config.add_subpackage('pysdr')

    return config

if __name__ == "__main__":
    from numpy.distutils.core import setup
    setup(name='PySDR',
          author='Martin Poviser',
          author_email='martin.povik@gmail.com',
          license='GPL',
          version='0.1dev',
          url='http://www.github.com/MLAB-project/pysdr',
          configuration=configuration,
          requires=['numpy', 'pyopengl', 'scipy'],
          scripts=['pysdr-recviewer', 'pysdr-waterfall'])
