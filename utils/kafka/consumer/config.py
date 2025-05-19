"""Configuration for consumer."""
from code_indexing.consumer import process_file
from config.settings import loaded_config
from etl.consumer import etl_external_data
from utils.kafka.constants import ALMANAC_GROUP_ID, KAFKA_SERVICE_CONFIG_MAPPING, FILE_INDEXING, \
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
        FILE_INDEXING: {
            "service_name": KafkaServices.almanac,
            "deserialization_format": KAFKA_SERIALIZATION_FORMAT,
            "consumer_config": COMMON_CONSUMER_CONFIG,
            "topics_configurations": {
                KAFKA_SERVICE_CONFIG_MAPPING[KafkaServices.almanac][FILE_INDEXING]["topics"][0]: {
                    # "tasks": [consume_local_node_sync]
                    "tasks": [process_file]
                }
            },
            "async_kafka": False,
        },
        ETL_EXTERNAL_DATA: {
            "service_name": KafkaServices.almanac,
            "deserialization_format": KAFKA_SERIALIZATION_FORMAT,
            "consumer_config": COMMON_CONSUMER_CONFIG,
            "topics_configurations": {
                KAFKA_SERVICE_CONFIG_MAPPING[KafkaServices.almanac][ETL_EXTERNAL_DATA]["topics"][0]: {
                    "tasks": [etl_external_data]
                }
            },
            "async_kafka": False,
        }
        # ,
        # "almanac_external_data_status_update_consumer": {
        #     "service_name": KafkaServices.almanac,
        #     "deserialization_format": KAFKA_SERIALIZATION_FORMAT,
        #     "consumer_config": COMMON_CONSUMER_CONFIG,
        #     "topics_configurations": {
        #         KAFKA_SERVICE_CONFIG_MAPPING[KafkaServices.almanac][EXTERNAL_DATA_STATUS_UPDATE_TOPIC]["topics"][0]: {
        #             "tasks": [etl_update_status]
        #         }
        #     },
        #     "async_kafka": False,
        # }

    }
}
KAFKA_CONSUMER_SETTINGS.update(KAFKA_CONSUMER_CONFIG)
