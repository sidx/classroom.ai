from utils.kafka.constants import KafkaServices
from config.settings import loaded_config
KAFKA_COMMON_PRODUCER_CONFIG = {
    "service_name": KafkaServices.almanac,
    'producer_config': {
        'bootstrap_servers': loaded_config.kafka_bootstrap_servers,
        "enable_idempotence": True,
        "acks": "all",
    },
}
