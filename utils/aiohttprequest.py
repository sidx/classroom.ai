import aiohttp


class AioHttpRequest:

    def __init__(self):
        session = aiohttp.ClientSession()
        self.session = session

    def get_aiohttp_session(self):
        return self.session

    async def close_session(self):
        await self.session.close()
