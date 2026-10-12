from collections.abc import AsyncGenerator
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


class SchemaVersionError(RuntimeError):
    """The database is not stamped at the migrations' head revision."""


def build_engine(url: str) -> AsyncEngine:
    """Create the async SQLAlchemy engine.

    Pool size is sized explicitly (10 + 20 overflow = 30 concurrent
    connections) so the request-concurrency limit is a stated decision
    rather than SQLAlchemy's default of 5 + 10.
    """
    return create_async_engine(url, pool_size=10, max_overflow=20, pool_pre_ping=True)


def build_sessionmaker(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the engine."""
    return async_sessionmaker(engine, expire_on_commit=False)


def _script_directory() -> ScriptDirectory:
    """The migration scripts, located independently of the working directory.

    `script_location` in alembic.ini is relative and would otherwise resolve
    against the process's cwd, which is not ours to assume.
    """
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_ALEMBIC_INI.parent / "alembic"))
    return ScriptDirectory.from_config(config)


async def verify_schema_is_current(engine: AsyncEngine) -> None:
    """Raise SchemaVersionError unless the database is at the migrations' head.

    A gateway started against a database with no schema (or an older one) still
    answers /health and /health/db, so an orchestrator sees a healthy instance
    while every /chat forwards the prompt to the provider and only then fails
    to audit it. A process that is alive but can never serve is worse than an
    absent one, so refuse to start instead.
    """
    head = _script_directory().get_current_head()
    async with engine.connect() as connection:
        current = await connection.run_sync(
            lambda sync_connection: MigrationContext.configure(
                sync_connection
            ).get_current_revision()
        )
    if current != head:
        raise SchemaVersionError(
            f"database schema is at revision {current!r} but the migrations' "
            f"head is {head!r}; run `alembic upgrade head`"
        )


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session from the app's sessionmaker."""
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session
