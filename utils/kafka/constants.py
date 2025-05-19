FILE_INDEXING = 'file_indexing'
ETL_EXTERNAL_DATA = "etl_external_data"
# EXTERNAL_DATA_STATUS_UPDATE_TOPIC = "external_data_status_update_topic"
FILE_INDEXING_TOPIC = "fex_almanac_file_indexing"
ETL_EXTERNAL_DATA_TOPIC = "fex_almanac_etl_external_data"

class KafkaServices:
    almanac = "almanac"


ALMANAC_GROUP_ID = "almanac-group-id"

KAFKA_SERVICE_CONFIG_MAPPING = {
    KafkaServices.almanac: {
        FILE_INDEXING: {
            "topics": [FILE_INDEXING_TOPIC],
            "group_id": ALMANAC_GROUP_ID,
        },
        ETL_EXTERNAL_DATA: {
            "topics": [ETL_EXTERNAL_DATA_TOPIC],
            "group_id": ALMANAC_GROUP_ID,
        }
        # ,
        # EXTERNAL_DATA_STATUS_UPDATE_TOPIC: {
        #     "topics": [EXTERNAL_DATA_STATUS_UPDATE_TOPIC],
        #     "group_id": ALMANAC_GROUP_ID,
        # }
    }
}
