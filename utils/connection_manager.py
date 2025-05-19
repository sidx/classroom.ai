from asyncio import current_task

from sqlalchemy.ext.asyncio import create_async_engine, async_scoped_session, AsyncSession
from sqlalchemy.orm import sessionmaker

from utils.sqlalchemy import async_db_url


class ConnectionManager:

    def __init__(self, db_url, db_echo, redis_url=None):
        self.db_url = db_url
        self.db_echo = db_echo
        # self.redis_url = redis_url
        self._db_engine, self._db_session_factory = self._setup_db()
        # _redis_pool = self._setup_redis()
        # self._redis_pool = _redis_pool

    def get_session_factory(self):
        return self._db_session_factory

    # def get_redis_pool(self):
    #     return self._redis_pool

    def _setup_db(self):
        engine = create_async_engine(str(self.db_url), echo=self.db_echo)
        session_factory = async_scoped_session(
            sessionmaker(
                engine,
                expire_on_commit=False,
                class_=AsyncSession,
            ),
            scopefunc=current_task,
        )
        return engine, session_factory

    # def _setup_redis(self):
    #     return ConnectionPool.from_url(
    #         str(self.redis_url),
    #     )

    async def close_connections(self):
        await self._db_engine.dispose()
        # await self._redis_pool.disconnect()
