import logging
import sys
import os

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

logging.basicConfig(stream=sys.stdout, level=LOG_LEVEL)
logging.getLogger(__name__)


def get_logger():
    return logging
