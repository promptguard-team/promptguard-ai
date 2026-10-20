import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import require_ciso
from app.models import AuditAction, AuditEvent, MLStatus, User
from app.schemas import (
    AuditEventDetail,
    AuditEventPage,
    AuditEventSummary,
    AuditStats,
)

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


@dataclass(frozen=True)
class TimeWindow:
    """A half-open [start, end) range on created_at, in UTC; None is unbounded."""

    start: datetime | None
    end: datetime | None


def time_window(
    from_: AwareDatetime | None = Query(None, alias="from"),
    to: AwareDatetime | None = Query(None),
) -> TimeWindow:
    """Parse ?from=&to=. AwareDatetime already rejects naive input with a 422:
    the dashboard runs in Europe/Warsaw and the column is UTC, so guessing
    either way would silently shift every window.
    """
    if from_ is not None and to is not None and from_ >= to:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'from' must be earlier than 'to'",
        )
    # Converted before querying because SQLite stores the wall-clock digits and
    # drops the offset, so a +02:00 bound would compare as if it were UTC.
    return TimeWindow(
        start=from_.astimezone(timezone.utc) if from_ is not None else None,
        end=to.astimezone(timezone.utc) if to is not None else None,
    )


def _window_clauses(window: TimeWindow) -> list[ColumnElement[bool]]:
    clauses = []
    if window.start is not None:
        clauses.append(AuditEvent.created_at >= window.start)
    if window.end is not None:
        clauses.append(AuditEvent.created_at < window.end)
    return clauses


@router.get("/events", response_model=AuditEventPage)
async def list_events(
    action: list[AuditAction] | None = Query(None),
    flagged: bool | None = None,
    ml_status: MLStatus | None = None,
    user_id: uuid.UUID | None = None,
    window: TimeWindow = Depends(time_window),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> AuditEventPage:
    """List audit event metadata, newest first. Never includes prompt text."""
    clauses = _window_clauses(window)
    if action:
        clauses.append(AuditEvent.action.in_(action))
    if flagged is not None:
        clauses.append(AuditEvent.flagged == flagged)
    if ml_status is not None:
        clauses.append(AuditEvent.ml_status == ml_status)
    if user_id is not None:
        clauses.append(AuditEvent.user_id == user_id)

    total = await session.scalar(
        select(func.count()).select_from(AuditEvent).where(*clauses)
    )
    result = await session.execute(
        select(AuditEvent, User.email)
        .join(User, AuditEvent.user_id == User.id)
        .where(*clauses)
        # id breaks ties: rows with equal created_at would otherwise come back
        # in an unspecified order and could appear on two pages or on none.
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return AuditEventPage(
        items=[_to_schema(AuditEventSummary, event, email) for event, email in result],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=AuditStats)
async def get_stats(
    window: TimeWindow = Depends(time_window),
    session: AsyncSession = Depends(get_session),
) -> AuditStats:
    """Count audit events in a time window, without loading any rows."""
    clauses = _window_clauses(window)
    by_action = {action.value: 0 for action in AuditAction}
    grouped = await session.execute(
        select(AuditEvent.action, func.count())
        .where(*clauses)
        .group_by(AuditEvent.action)
    )
    for action, count in grouped:
        by_action[action.value] = count

    counts = await session.execute(
        select(
            func.count().filter(AuditEvent.flagged.is_(True)),
            func.count().filter(AuditEvent.ml_status == MLStatus.unavailable),
        ).where(*clauses)
    )
    flagged, ml_unavailable = counts.one()
    return AuditStats(
        total=sum(by_action.values()),
        by_action=by_action,
        flagged=flagged,
        ml_unavailable=ml_unavailable,
    )


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
