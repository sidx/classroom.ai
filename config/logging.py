import inspect
from datetime import datetime
import structlog, logging
from structlog import contextvars
from structlog.stdlib import BoundLogger
from structlog_sentry import SentryProcessor

from config.settings import loaded_config
from utils.constants import UTC_TIME_ZONE
from pytz import timezone

def get_current_time(time_zone: str = UTC_TIME_ZONE):
    return datetime.now(timezone(time_zone))

def add_call_stack(_, __, event_dict):
    record = event_dict.get("_record")
    if record and record.levelno >= logging.ERROR:
        event_dict["call_stack"] = get_call_stack()
    return event_dict


def get_logger(*args, **kwargs) -> BoundLogger:
    """Create structlog logger for logging."""
    if loaded_config.env.lower() == "local":
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            SentryProcessor(level=logging.ERROR),
            structlog.processors.format_exc_info,
            add_call_stack,
            renderer
        ],
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger(**kwargs)


def get_call_stack():
    stack = inspect.stack()
    call_stack = []
    for frame_info in stack[1:5]:  # Skip the current frame
        call_stack.append({
            "function": frame_info.function,
            "file": frame_info.filename,
            "line": frame_info.lineno
        })
    return call_stack

logger = get_logger()