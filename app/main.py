import uvicorn
from config.settings import loaded_config


def main() -> None:
    """Entrypoint of the application."""
    # import newrelic.agent

    # newrelic.agent.initialize('newrelic.ini')
    uvicorn.run(
        "app.application:get_app",
        workers=loaded_config.workers_count,
        host=loaded_config.host,
        port=loaded_config.port,
        reload=loaded_config.debug,
        # log_level=loaded_config.log_level.value.lower(),
        factory=True,
    )
