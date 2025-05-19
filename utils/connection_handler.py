from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import loaded_config
from utils.kafka import AsyncEventEmitterWrapper


class ConnectionHandler:

    def __init__(self, connection_manager=None, event_bridge=None):
        self._session: Optional[AsyncSession] = None
        self._connection_manager = connection_manager
        self._event_emitter: Optional[AsyncEventEmitterWrapper] = None

    @property
    def session(self):
        if not self._session:
            session_factory = self._connection_manager.get_session_factory()
            self._session = session_factory()
        return self._session

    @property
    def event_emitter(self):
        if not self._event_emitter:
            # self._event_emitter = AsyncEventEmitterWrapper(event_emitter=self._event_bridge.event_emitter)
            self._event_emitter = AsyncEventEmitterWrapper()
        return self._event_emitter

    async def session_commit(self):
        await self.session.commit()

    async def close(self):
        if self._session:
            await self._session.close()
        # if self._redis_connection:
        #     await self._redis_connection.close()


async def get_connection_handler_for_app():
    connection_handler = ConnectionHandler(
        connection_manager=loaded_config.connection_manager
        # event_bridge=loaded_config.async_event_bridge
    )
    try:
        yield connection_handler
    finally:
        await connection_handler.close()


