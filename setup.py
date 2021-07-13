from distutils.core import setup

setup(
    name='gpsrenda',
    version='0.1.0',
    description='Renda gauges onto video from a .fit file',
    author='Joshua Wise, Noah Young',
    packages=['gpsrenda'],
    scripts=['gpsrenda/bin/renda'],
    install_requires=[
        'fitparse',
        'moviepy',
        'numpy',
        'pycairo',
        'pytz',
        'pyyaml',
        'scipy',
        'tzlocal',
    ]
)
