from datetime import datetime
from pytz import timezone
from sqlalchemy import TypeDecorator, DateTime, Column
from sqlalchemy.orm import declarative_mixin, Mapped, declarative_base
from urllib.parse import urlparse, urlunparse

from utils.constants import UTC_TIME_ZONE


def get_current_time(time_zone: str = UTC_TIME_ZONE):
    return datetime.now(timezone(time_zone))


def async_db_url(db_url: str):
    parsed_url = urlparse(db_url)
    new_scheme = "postgresql+asyncpg"
    netloc = f"{parsed_url.username}:{parsed_url.password}@{parsed_url.hostname}:{parsed_url.port}"
    updated_db_url = urlunparse((new_scheme, netloc, parsed_url.path, '', '', ''))
    return updated_db_url


@declarative_mixin
class TimestampMixin:
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=get_current_time)
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), default=get_current_time,
                                          onupdate=get_current_time)


Base = declarative_base()
