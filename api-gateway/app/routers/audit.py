import uuid
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import require_ciso
from app.models import AuditEvent, User
from app.schemas import AuditEventDetail

router = APIRouter(
    prefix="/audit", tags=["audit"], dependencies=[Depends(require_ciso)]
)


# A TypeVar rather than PEP 695 syntax: the image and CI run Python 3.11.
SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _to_schema(schema: type[SchemaT], event: AuditEvent, user_email: str) -> SchemaT:
    """Build `schema` from an event's columns plus its author's email."""
    values = {
        name: getattr(event, name)
        for name in schema.model_fields
        if name != "user_email"
    }
    return schema(**values, user_email=user_email)


@router.get("/events/{event_id}", response_model=AuditEventDetail)
async def get_event(
    event_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> AuditEventDetail:
    """Return one audit event, including its prompt and response text."""
    result = await session.execute(
        select(AuditEvent, User.email)
        .join(User, AuditEvent.user_id == User.id)
        .where(AuditEvent.id == event_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="audit event not found")
    event, user_email = row
    return _to_schema(AuditEventDetail, event, user_email)
