"""Seeding helpers for the /audit suites.

Events are inserted directly rather than through /chat, so each test controls
created_at exactly instead of depending on the database clock.
"""

import uuid
from datetime import datetime

from sqlalchemy import select

from app.models import AuditAction, AuditEvent, User


async def user_id_of(app, email: str) -> uuid.UUID:
    async with app.state.sessionmaker() as session:
        result = await session.execute(select(User.id).where(User.email == email))
        return result.scalar_one()


async def add_event(
    app,
    *,
    user_id: uuid.UUID,
    created_at: datetime,
    action: AuditAction = AuditAction.allowed,
    prompt: str = "a prompt",
    **fields,
) -> uuid.UUID:
    event = AuditEvent(
        user_id=user_id, created_at=created_at, action=action, prompt=prompt, **fields
    )
    async with app.state.sessionmaker() as session:
        session.add(event)
        await session.commit()
    return event.id
