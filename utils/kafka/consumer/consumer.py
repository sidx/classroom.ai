import asyncio

from eventqueue.queue_consumer import setup_and_start_consumer
from eventqueue.queue_health import _healthz, _readyz, health_check

from config.settings import loaded_config
from utils.kafka.constants import KafkaServices
from utils.kafka.consumer.config import KAFKA_CONSUMER_SETTINGS
from utils.load_config import run_on_consumer_exit, run_on_consumer_startup


async def main():
    try:
        await run_on_consumer_startup()
        
        # Initialize health check
        await health_check.start()
        
        # Start consumer
        consumer = await setup_and_start_consumer(
            KAFKA_CONSUMER_SETTINGS[KafkaServices.almanac][loaded_config.CONSUMER_TYPE]
        )
        
        # Start health check tasks
        asyncio.create_task(_healthz())
        asyncio.create_task(_readyz())

        all_tasks = asyncio.all_tasks()
        executed_tasks = asyncio.gather(*all_tasks, return_exceptions=True)
        results = await executed_tasks
        for result in results:
            if isinstance(result, Exception):
                # Handle the exception (log it, re-raise, etc.)
                print(f"Exception in a task: {result}")
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        await run_on_consumer_exit()
        if 'health_check' in locals():
            await health_check.stop()
