import logging

from .defaults import *  # noqa

logger = logging.getLogger(__name__)

try:
    from .local import *  # noqa
except ImportError:
    logger.warning('No addons.workflow local settings found')
