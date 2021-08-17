import logging

logger = logging.getLogger(__file__)

try:
    from . import moviepy
    logger.debug("successfully loaded moviepy")
except:
    logger.debug("failed to load moviepy")

try:
    from . import gstreamer
    logger.debug("successfully loaded gstreamer")
except:
    logger.debug("failed to load gstreamer")

from .engines import engines, default_engine
