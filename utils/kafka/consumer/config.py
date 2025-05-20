"""Configuration for consumer."""
from config.settings import loaded_config
from kb.consumer import knowledge_base_consumer
from utils.kafka.constants import ALMANAC_GROUP_ID, KAFKA_SERVICE_CONFIG_MAPPING, \
    ETL_EXTERNAL_DATA
from utils.kafka.producer.config import KafkaServices


KAFKA_SERIALIZATION_FORMAT = "json"
KAFKA_SESSION_TIMEOUT_IN_MS = 20000
KAFKA_OFFSET_RESET_STRATEGY = "latest"

KAFKA_CONSUMER_SETTINGS = {}

COMMON_CONSUMER_CONFIG = {
    "bootstrap.servers": loaded_config.kafka_bootstrap_servers,
    "session.timeout.ms": KAFKA_SESSION_TIMEOUT_IN_MS,
    "default.topic.config": {"auto.offset.reset": KAFKA_OFFSET_RESET_STRATEGY},
    "group.id": ALMANAC_GROUP_ID,
}

KAFKA_CONSUMER_CONFIG = {
    KafkaServices.almanac: {
        ETL_EXTERNAL_DATA: {
            "service_name": KafkaServices.almanac,
            "deserialization_format": KAFKA_SERIALIZATION_FORMAT,
            "consumer_config": COMMON_CONSUMER_CONFIG,
            "topics_configurations": {
                KAFKA_SERVICE_CONFIG_MAPPING[KafkaServices.almanac][ETL_EXTERNAL_DATA]["topics"][0]: {
                    "tasks": [knowledge_base_consumer]
                }
            },
            "async_kafka": False,
        }
    }
}
KAFKA_CONSUMER_SETTINGS.update(KAFKA_CONSUMER_CONFIG)
