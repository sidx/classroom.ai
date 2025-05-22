import enum
import os

from pydantic_settings import BaseSettings

from config.config_parser import docker_args
from utils.aiohttprequest import AioHttpRequest
from utils.connection_manager import ConnectionManager
from utils.sqlalchemy import async_db_url
from typing import ClassVar, Optional, Dict

args = docker_args


class LogLevel(enum.Enum):  # noqa: WPS600
    """Possible log levels."""

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class Settings(BaseSettings):

    CONSUMER_TYPE: str = args.consumer_type
    env: str = args.env
    port: int = args.port
    host: str = args.host
    debug: bool = args.debug
    workers_count: int = 1
    mode: str = args.mode
    postgres_fynix_almanac_read_write: str = args.postgres_fynix_almanac_read_write
    db_url: str = async_db_url(args.postgres_fynix_almanac_read_write)
    db_echo: bool = args.debug
    server_type: str = args.server_type
    BASE_DIR: ClassVar[str] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    POD_NAMESPACE: str = args.K8S_POD_NAMESPACE
    NODE_NAME: str = args.K8S_NODE_NAME
    POD_NAME: str = args.K8S_POD_NAME
    openai_gpt4o_api_key: str = args.openai_gpt4o_api_key
    sentry_sample_rate: float = 1.0
    sentry_environment: str = args.sentry_environment
    sentry_dsn: str = args.sentry_dsn
    # realm: str = args.realm
    log_level: str = LogLevel.INFO.value
    elastic_search_url: str = args.elastic_search_url

    """ global class instances """
    connection_manager: Optional[ConnectionManager] = None
    read_connection_manager: Optional[ConnectionManager] = None
    aiohttp_request: Optional[AioHttpRequest] = None
    model_mappings: Optional[Dict] = {}
    embedding_mappings: Optional[Dict] = {}
    kafka_bootstrap_servers: str = args.kafka_broker_list


loaded_config = Settings()
