from distutils.core import setup

setup(
    name='GPS Renda',
    version='0.1.0',
    description='Render guages onto video from a .fit file',
    author='Joshua Wise',
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
