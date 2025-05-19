from config.settings import loaded_config

if loaded_config.mode == "server":
    from app.main import main as server_main

    if __name__ == "__main__":
        server_main()
elif loaded_config.mode == "consumer":
    import asyncio
    from utils.kafka.consumer.consumer import main as consumer_main

    print("Starting Consumer")
    asyncio.run(consumer_main())
else:
    print('MODE not available')
