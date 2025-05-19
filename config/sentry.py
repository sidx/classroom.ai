import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from config.settings import loaded_config


def configure_sentry():
    with open(f"{loaded_config.BASE_DIR}/gitsha", "r") as file:
        gitsha = file.readline()

    sentry_sdk.init(
        dsn=loaded_config.sentry_dsn,
        traces_sample_rate=loaded_config.sentry_sample_rate,
        environment=loaded_config.sentry_environment,
        release=gitsha,  # need to add release version in gitsha file
        integrations=[
            LoggingIntegration(
                level=logging.getLevelName(loaded_config.log_level.upper()),  # Capture info and above as breadcrumbs
                event_level=logging.ERROR,  # Send errors as events
            ),
            SqlalchemyIntegration(),
        ],
    )
