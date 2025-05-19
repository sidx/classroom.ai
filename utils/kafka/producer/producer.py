from typing import List
from eventbridge.constants import DEFAULT_DESERIALIZATION_FORMAT, DEFAULT_HASH_FLAG
from eventbridge.emitter import AsyncEventEmitter

from utils.kafka.producer.config import KAFKA_COMMON_PRODUCER_CONFIG
from utils.singleton import Singleton


class AsyncEventBridge(metaclass=Singleton):
    """Class AsyncEventBridge."""

    def __init__(self, configurations=KAFKA_COMMON_PRODUCER_CONFIG, *args, **kwargs):
        self.event_emitter = AsyncEventEmitter(configurations)

    async def stop_producer(self):
        if self.event_emitter.kafka_producer and self.event_emitter.kafka_producer.producer:
            await self.event_emitter.kafka_producer.stop_producer()


class AsyncEventEmitterWrapper:

    def __init__(self, *args, **kwargs):
        self.event_emitter = AsyncEventBridge(*args, **kwargs).event_emitter
        self.event_queue: List = []

    def add_event_to_queue(self, *,
                           topics, partition_value,
                           event, event_meta={},
                           serialization_format=DEFAULT_DESERIALIZATION_FORMAT,
                           hash_flag=DEFAULT_HASH_FLAG, callback=False, headers=None):
        event_dict = {
            'topics': topics,
            'partition_value': partition_value,
            'event': event,
            'event_meta': event_meta,
            'serialization_format': serialization_format,
            'hash_flag': hash_flag,
            'callback': callback,
            'headers': headers
        }
        self.event_queue.append(event_dict)

    async def emit(self, *args, **kwargs):
        return await self.event_emitter.emit(*args, **kwargs)

    async def produce_event(self, *args, **kwargs):
        return await self.event_emitter.produce_event(*args, **kwargs)

    async def emit_events(self):
        for event in self.event_queue:
            try:
                response = await self.event_emitter.emit(
                    topics=event["topics"],
                    partition_value=event["partition_value"],
                    event=event["event"],
                    event_meta=event["event_meta"],
                    serialization_format=event["serialization_format"],
                    hash_flag=event["hash_flag"],
                    callback=event["callback"],
                    headers=event["headers"]
                )
            except Exception as e:
                pass
        self.clear_queue()

    def clear_queue(self):
        self.event_queue = []
