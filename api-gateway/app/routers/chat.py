from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.deps import get_current_user, get_llm_client, get_sessionmaker
from app.llm import LLMClient, LLMError
from app.models import AuditAction, AuditEvent, User
from app.rules import scan_text
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


async def _audit(
    sessionmaker: async_sessionmaker[AsyncSession],
    user: User,
    action: AuditAction,
    prompt: str,
    response: str | None = None,
    rule: str | None = None,
) -> None:
    """Persist one audit event for the request's outcome.

    Opens its own short-lived session rather than reusing one held across
    the request, so no pooled connection sits open during the provider
    round-trip in `chat()`.
    """
    async with sessionmaker() as session:
        session.add(
            AuditEvent(
                user_id=user.id,
                action=action,
                prompt=prompt,
                response=response,
                rule=rule,
            )
        )
        await session.commit()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    sessionmaker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
    llm: LLMClient = Depends(get_llm_client),
) -> ChatResponse:
    """Proxy a prompt to the LLM provider with inspection in both directions."""
    prompt_match = scan_text(body.prompt)
    if prompt_match is not None:
        await _audit(
            sessionmaker,
            user,
            AuditAction.blocked_prompt,
            body.prompt,
            rule=prompt_match.rule,
        )
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="prompt blocked by content policy",
        )

    try:
        reply = await llm.complete(body.prompt)
    except LLMError as exc:
        # The prompt may have reached the provider even though no usable
        # response came back, so the attempt is audited either way.
        await _audit(sessionmaker, user, AuditAction.allowed, body.prompt)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="LLM provider unavailable"
        ) from exc

    response_match = scan_text(reply)
    if response_match is not None:
        await _audit(
            sessionmaker,
            user,
            AuditAction.blocked_response,
            body.prompt,
            response=reply,
            rule=response_match.rule,
        )
        return ChatResponse(
            response="[response blocked by PromptGuard: content policy]",
            blocked=True,
        )

    await _audit(sessionmaker, user, AuditAction.allowed, body.prompt, response=reply)
    return ChatResponse(response=reply)
