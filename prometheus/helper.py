import logging
import os

from prometheus_client import generate_latest

from config.logging import logger
# from config.docker_config import loaded_config
from config.settings import loaded_config
from prometheus.metrics import REGISTRY

BASE_DIR = loaded_config.BASE_DIR
POD_NAMESPACE = loaded_config.POD_NAMESPACE
NODE_NAME = loaded_config.NODE_NAME
POD_NAME = loaded_config.POD_NAME

# logger setup
PROM_LOGGER = logging.getLogger(__name__)
PROM_LOGGER.setLevel(logging.DEBUG)
METRICS_DIR = os.getenv("METRICS_DIR")
LOG_FILE = f'{METRICS_DIR}/{POD_NAME}.prom'

# For local support
if POD_NAME == 'temp':
    LOG_FILE = f"{BASE_DIR}/logs.prom"

FORMATTER = logging.Formatter('%(message)s')


async def generate_prometheus_data():
    with open(LOG_FILE, mode='w', encoding='utf-8') as file:
        data = generate_latest(registry=REGISTRY).decode('utf-8', errors='ignore')
        file.write(data)
