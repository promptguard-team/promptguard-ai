import logging
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.classifier import ClassifierClient, ClassifierError
from app.config import Settings, get_settings
from app.deps import (
    get_classifier_client,
    get_current_user,
    get_llm_client,
    get_sessionmaker,
)
from app.llm import LLMClient, LLMError
from app.models import AuditAction, AuditEvent, MLStatus, User
from app.rules import scan_text
from app.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@dataclass
class AuditDraft:
    """Facts about one request, accumulated as they become known.

    A single write site per outcome still has to be called before each
    `raise`, but collecting the fields here means no exit path can record an
    inconsistent subset of them.
    """

    user_id: uuid.UUID
    prompt: str
    action: AuditAction = AuditAction.allowed
    rule: str | None = None
    response: str | None = None
    ml_status: MLStatus = MLStatus.skipped
    ml_score: float | None = None
    ml_label: str | None = None
    ml_model_version: str | None = None
    flagged: bool = False

    def to_event(self) -> AuditEvent:
        return AuditEvent(
            user_id=self.user_id,
            action=self.action,
            rule=self.rule,
            prompt=self.prompt,
            response=self.response,
            ml_status=self.ml_status,
            ml_score=self.ml_score,
            ml_label=self.ml_label,
            ml_model_version=self.ml_model_version,
            flagged=self.flagged,
        )


async def _write(
    sessionmaker: async_sessionmaker[AsyncSession], draft: AuditDraft
) -> None:
    """Persist the request's single audit event.

    Opens its own short-lived session so no pooled connection is held during
    the provider round-trip.
    """
    async with sessionmaker() as session:
        session.add(draft.to_event())
        await session.commit()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    sessionmaker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
    llm: LLMClient = Depends(get_llm_client),
    classifier: ClassifierClient = Depends(get_classifier_client),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    """Proxy a prompt to the LLM provider with inspection in both directions."""
    draft = AuditDraft(user_id=user.id, prompt=body.prompt)
    blocked = HTTPException(
        status.HTTP_403_FORBIDDEN, detail="prompt blocked by content policy"
    )

    prompt_match = scan_text(body.prompt)
    if prompt_match is not None:
        # A rule match is a hard block; there is nothing left to score, so
        # ml_status stays `skipped`.
        draft.action = AuditAction.blocked_prompt
        draft.rule = prompt_match.rule
        await _write(sessionmaker, draft)
        raise blocked

    try:
        verdict = await classifier.classify(body.prompt)
    except ClassifierError as exc:
        # Fail open: Layer 1 still ran, and severing all LLM access during our
        # own outage would drive users around the proxy entirely. Log it: a
        # mistyped CLASSIFIER_URL disables Layer 2 indefinitely, and the audit
        # table is the only other place this degradation is visible.
        logger.warning("classifier unavailable, failing open: %s", exc)
        draft.ml_status = MLStatus.unavailable
    else:
        draft.ml_status = MLStatus.ok
        draft.ml_score = verdict.score
        draft.ml_label = verdict.label
        draft.ml_model_version = verdict.model_version
        if verdict.score >= settings.classifier_block_threshold:
            draft.action = AuditAction.blocked_prompt
            await _write(sessionmaker, draft)
            raise blocked
        # Set only past the block check: `flagged` means "allowed but needs
        # review", so a blocked row must never enter the review queue.
        draft.flagged = verdict.score >= settings.classifier_review_threshold

    try:
        reply = await llm.complete(body.prompt)
    except LLMError as exc:
        draft.action = AuditAction.provider_error
        await _write(sessionmaker, draft)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="LLM provider unavailable"
        ) from exc

    draft.response = reply
    response_match = scan_text(reply)
    if response_match is not None:
        draft.action = AuditAction.blocked_response
        draft.rule = response_match.rule
        await _write(sessionmaker, draft)
        return ChatResponse(
            response="[response blocked by PromptGuard: content policy]",
            blocked=True,
        )

    draft.action = AuditAction.allowed
    await _write(sessionmaker, draft)
    return ChatResponse(response=reply)
