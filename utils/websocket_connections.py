from config.settings import loaded_config


async def close_ws_connections():
    # Connection reset time - 3AM IST

    for ws in list(loaded_config.ws_connections):
        await ws.close()
        loaded_config.ws_connections.remove(ws)


