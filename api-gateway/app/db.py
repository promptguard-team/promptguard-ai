from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


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


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session from the app's sessionmaker."""
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session
