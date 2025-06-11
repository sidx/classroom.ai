import asyncio
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine
from alembic import context

from config.settings import loaded_config
from utils.sqlalchemy import Base


from fex_utilities.threads.models import *
import kb.models

config = context.config
config.set_main_option("sqlalchemy.url", loaded_config.db_url)


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


from kb.models import *
target_metadata = [Base.metadata]


def include_object(object, name, type_, reflected, compare_to):
    # Keep all tables present in the database
    if type_ == "table" and reflected:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=include_object,
        dialect_opts={"paramstyle": "named"}
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata,
                      compare_type=True, include_object=include_object
                      )

    with context.begin_transaction():
        context.run_migrations()

    # insert_initial_data(connection)

def insert_initial_data(connection: Connection) -> None:
    """Insert initial data after migration, avoiding transaction issues."""
    connection.execute(
        text("""
            INSERT INTO external_data_source (name, created_at, updated_at)
            SELECT 'stackoverflow', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM external_data_source WHERE name = 'stackoverflow'
            )
        """)
    )
    connection.commit()

async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = AsyncEngine(
        engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            future=True,
        )
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
