import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.classifier import ClassifierClient
from app.llm import LLMClient
from app.models import User, UserRole
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    """Return the session factory created in the lifespan."""
    return request.app.state.sessionmaker


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    sessionmaker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
) -> User:
    """Resolve the authenticated, active user from the Bearer token."""
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise unauthorized from None

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise unauthorized
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise unauthorized from None

    # A short-lived session, closed before the caller does anything else
    # (notably, before the /chat handler's provider round-trip) so the
    # pooled connection isn't held for the request's full duration. Safe to
    # return the detached User: the sessionmaker uses expire_on_commit=False
    # and nothing commits here, so id/email/role/is_active (exactly what
    # UserRead serialises) stay loaded on the instance.
    async with sessionmaker() as session:
        user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_ciso(user: User = Depends(get_current_user)) -> User:
    """Allow only users whose stored role is ciso.

    The role is read from the row get_current_user just loaded, never from the
    token's role claim, so revoking the role takes effect on the next request
    instead of when the token expires.
    """
    if user.role is not UserRole.ciso:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="ciso role required")
    return user


def get_llm_client(request: Request) -> LLMClient:
    """Return the shared LLM client created in the lifespan."""
    return request.app.state.llm_client


def get_classifier_client(request: Request) -> ClassifierClient:
    """Return the shared classifier client created in the lifespan."""
    return request.app.state.classifier_client
