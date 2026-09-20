import uuid
from datetime import datetime

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.models import AuditAction, AuditEvent, Base, MLStatus, User


@pytest_asyncio.fixture
async def session():
    """Provide a session bound to a fresh in-memory SQLite database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db_session:
        yield db_session
    await engine.dispose()


async def test_audit_event_roundtrip(session: AsyncSession):
    user = User(email="a@example.com", hashed_password="h")
    session.add(user)
    await session.commit()

    event = AuditEvent(
        user_id=user.id,
        action=AuditAction.blocked_prompt,
        prompt="here is AKIAIOSFODNN7EXAMPLE",  # pragma: allowlist secret
        rule="aws_access_key",
    )
    session.add(event)
    await session.commit()

    result = await session.execute(
        select(AuditEvent).where(AuditEvent.user_id == user.id)
    )
    fetched = result.scalar_one()
    assert isinstance(fetched.id, uuid.UUID)
    assert fetched.action == AuditAction.blocked_prompt
    assert fetched.rule == "aws_access_key"
    assert fetched.response is None
    assert isinstance(fetched.created_at, datetime)


async def test_audit_event_defaults(session: AsyncSession):
    user = User(email="b@example.com", hashed_password="h")
    session.add(user)
    await session.commit()

    event = AuditEvent(
        user_id=user.id, action=AuditAction.allowed, prompt="hi", response="hello"
    )
    session.add(event)
    await session.commit()

    result = await session.execute(
        select(AuditEvent).where(AuditEvent.user_id == user.id)
    )
    fetched = result.scalar_one()
    assert fetched.rule is None
    assert fetched.response == "hello"


def test_provider_error_action_exists():
    assert AuditAction.provider_error.value == "provider_error"


def test_ml_status_members():
    assert {s.value for s in MLStatus} == {"skipped", "ok", "unavailable"}


async def test_audit_event_defaults_to_skipped_and_unflagged(app):
    import uuid

    from sqlalchemy import select

    from app.models import AuditEvent, User
    from app.security import hash_password

    maker = app.state.sessionmaker
    async with maker() as session:
        user = User(
            id=uuid.uuid4(),
            email="ml@example.com",
            hashed_password=hash_password("secret123"),
        )
        session.add(user)
        await session.commit()
        session.add(
            AuditEvent(user_id=user.id, action=AuditAction.allowed, prompt="hi")
        )
        await session.commit()
        event = (await session.execute(select(AuditEvent))).scalars().one()
        assert event.ml_status == MLStatus.skipped
        assert event.flagged is False
        assert event.ml_score is None
        assert event.ml_label is None
        assert event.ml_model_version is None


async def test_audit_event_stores_a_verdict(app):
    import uuid

    from sqlalchemy import select

    from app.models import AuditEvent, User
    from app.security import hash_password

    maker = app.state.sessionmaker
    async with maker() as session:
        user = User(
            id=uuid.uuid4(),
            email="ml2@example.com",
            hashed_password=hash_password("secret123"),
        )
        session.add(user)
        await session.commit()
        session.add(
            AuditEvent(
                user_id=user.id,
                action=AuditAction.allowed,
                prompt="hi",
                ml_status=MLStatus.ok,
                ml_score=0.72,
                ml_label="injection",
                ml_model_version="stub-tfidf-0.1.0",
                flagged=True,
            )
        )
        await session.commit()
        event = (await session.execute(select(AuditEvent))).scalars().one()
        assert event.ml_score == 0.72
        assert event.ml_model_version == "stub-tfidf-0.1.0"
        assert event.flagged is True
