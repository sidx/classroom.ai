ETL_EXTERNAL_DATA = "etl_external_data"
ETL_EXTERNAL_DATA_TOPIC = "fex_almanac_etl_external_data"

class KafkaServices:
    almanac = "almanac"


ALMANAC_GROUP_ID = "almanac-group-id"

KAFKA_SERVICE_CONFIG_MAPPING = {
    KafkaServices.almanac: {
        ETL_EXTERNAL_DATA: {
            "topics": [ETL_EXTERNAL_DATA_TOPIC],
            "group_id": ALMANAC_GROUP_ID,
        }
    }
}
