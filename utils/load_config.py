from config.settings import loaded_config
from utils.connection_manager import ConnectionManager
from utils.aiohttprequest import AioHttpRequest
from spacy.cli import download



async def run_on_startup():
    try:
        await init_connections()
        # await init_scheduler()
    except Exception as e:
        print(e)


async def run_on_exit():
    await loaded_config.connection_manager.close_connections()
    await loaded_config.aiohttp_request.close_session()
    loaded_config.aps_scheduler.shutdown(wait=False)

async def run_on_consumer_exit():
    await loaded_config.connection_manager.close_connections()

async def init_connections():
    connection_manager = ConnectionManager(
        db_url=loaded_config.db_url,
        db_echo=loaded_config.db_echo
    )
    loaded_config.connection_manager = connection_manager
    loaded_config.aiohttp_request = AioHttpRequest()

async def run_on_consumer_startup():
    try:
        await init_consumer_connections()
        download('en_core_web_md')
    except Exception as e:
        print(e)

async def init_consumer_connections():
    connection_manager = ConnectionManager(
        db_url=loaded_config.db_url,
        db_echo=loaded_config.db_echo
    )
    loaded_config.connection_manager = connection_manager


