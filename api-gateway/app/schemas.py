import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import AuditAction, MLStatus, UserRole


def _lowercase_email(value: str) -> str:
    # email-validator only lowercases the domain part; without this, the
    # local part's casing would let one person hold several accounts that
    # the audit log and duplicate-email check both treat as distinct.
    return value.lower()


class RegisterRequest(BaseModel):
    """Payload for creating a new account."""

    email: EmailStr
    password: str = Field(min_length=8)

    _normalize_email = field_validator("email")(_lowercase_email)


class LoginRequest(BaseModel):
    """Payload for obtaining an access token."""

    email: EmailStr
    password: str

    _normalize_email = field_validator("email")(_lowercase_email)


class TokenResponse(BaseModel):
    """A bearer access token."""

    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    """Public representation of a user account."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    is_active: bool


class ChatRequest(BaseModel):
    """A user prompt to proxy to the LLM provider."""

    prompt: str = Field(min_length=1, max_length=32000)


class ChatResponse(BaseModel):
    """The (possibly blocked) reply returned to the user."""

    response: str
    blocked: bool = False


class AuditEventSummary(BaseModel):
    """Audit event metadata for the CISO list view.

    Deliberately carries no prompt or response text: the list is fetched on
    every dashboard visit, so text served here would be copied into browsers
    without anyone choosing to read it. Text is served by AuditEventDetail only.
    """

    id: uuid.UUID
    created_at: datetime
    user_id: uuid.UUID
    user_email: EmailStr
    action: AuditAction
    rule: str | None
    ml_status: MLStatus
    ml_score: float | None
    ml_label: str | None
    ml_model_version: str | None
    flagged: bool

    @field_validator("created_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        # SQLite returns naive values for DateTime(timezone=True); every stored
        # value is UTC, so both databases serialise identically.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class AuditEventDetail(AuditEventSummary):
    """One audit event including the prompt and response text."""

    prompt: str
    response: str | None


class AuditEventPage(BaseModel):
    """One page of audit event metadata."""

    items: list[AuditEventSummary]
    total: int
    limit: int
    offset: int


class AuditStats(BaseModel):
    """Audit event counts over a time window."""

    total: int
    by_action: dict[str, int]
    flagged: int
    # Requests that went through without a Layer 2 verdict (fail-open).
    ml_unavailable: int
