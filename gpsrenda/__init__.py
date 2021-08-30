#from . import video, widgets, fit
import logging

logger = logging.getLogger(__name__)

def km_to_mi(km):
    return km * 0.62137119

def c_to_f(c):
    return (c * 9 / 5) + 32
