import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditAction(str, enum.Enum):
    """Outcome of a proxied chat request."""

    allowed = "allowed"
    blocked_prompt = "blocked_prompt"
    blocked_response = "blocked_response"
    provider_error = "provider_error"


class MLStatus(str, enum.Enum):
    """Whether Layer 2 produced a verdict for this request."""

    skipped = "skipped"
    ok = "ok"
    unavailable = "unavailable"


class AuditEvent(Base):
    """One inspection record per proxied chat request."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction))
    rule: Mapped[str | None] = mapped_column(String(64), default=None)
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text, default=None)
    ml_status: Mapped[MLStatus] = mapped_column(
        Enum(MLStatus), default=MLStatus.skipped, server_default=text("'skipped'")
    )
    ml_score: Mapped[float | None] = mapped_column(Float, default=None)
    ml_label: Mapped[str | None] = mapped_column(String(32), default=None)
    ml_model_version: Mapped[str | None] = mapped_column(String(64), default=None)
    flagged: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
