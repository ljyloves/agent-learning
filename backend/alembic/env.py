"""Alembic environment for FlowGate's async SQLAlchemy engine."""

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401
from app.config import settings
from app.database import Base


config = context.config
target_metadata = Base.metadata
LANGGRAPH_CHECKPOINT_TABLES = frozenset(
    {
        "checkpoint_blobs",
        "checkpoint_migrations",
        "checkpoint_writes",
        "checkpoints",
    }
)


def include_flowgate_object(
    object_,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to,
) -> bool:
    """Leave LangGraph's versioned checkpoint tables to its own setup()."""

    if type_ == "table" and name in LANGGRAPH_CHECKPOINT_TABLES:
        return False
    table = getattr(object_, "table", None)
    if table is not None and table.name in LANGGRAPH_CHECKPOINT_TABLES:
        return False
    return True


def database_url() -> str:
    return settings.database_url.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_flowgate_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_flowgate_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
