from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import loaded_config
from eventqueue.queue_emitter import QueueEmitterWrapper
from utils.kafka.producer.config import KAFKA_COMMON_PRODUCER_CONFIG


class ConnectionHandler:

    def __init__(self, connection_manager=None):
        self._session: Optional[AsyncSession] = None
        self._connection_manager = connection_manager
        self._event_emitter: Optional[QueueEmitterWrapper] = None

    @property
    def session(self):
        if not self._session:
            session_factory = self._connection_manager.get_session_factory()
            self._session = session_factory()
        return self._session

    @property
    async def event_emitter(self):
        if not self._event_emitter:
            self._event_emitter = QueueEmitterWrapper(config=KAFKA_COMMON_PRODUCER_CONFIG)
            await self._event_emitter.initialize()
        return self._event_emitter

    async def session_commit(self):
        await self.session.commit()

    async def close(self):
        if self._session:
            await self._session.close()
        if self._event_emitter:
            await self._event_emitter.stop()


async def get_connection_handler_for_app():
    connection_handler = ConnectionHandler(
        connection_manager=loaded_config.connection_manager
    )
    try:
        yield connection_handler
    finally:
        await connection_handler.close()


