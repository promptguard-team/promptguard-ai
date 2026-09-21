import httpx
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.classifier import ClassifierClient
from app.llm import LLMClient
from app.main import create_app
from app.models import Base


@pytest_asyncio.fixture
async def app():
    """A FastAPI app wired to a fresh in-memory SQLite database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    application = create_app()
    application.state.engine = engine
    application.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    def _llm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "mock reply"}}]}
        )

    application.state.llm_client = LLMClient(
        api_base="https://llm.test/v1",
        api_key="test-key",
        model="test-model",
        transport=httpx.MockTransport(_llm_handler),
    )

    def _classifier_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"label": "clean", "score": 0.01, "model_version": "test-model-0"},
        )

    application.state.classifier_client = ClassifierClient(
        base_url="http://ml.test",
        transport=httpx.MockTransport(_classifier_handler),
    )

    yield application
    await engine.dispose()


@pytest_asyncio.fixture
async def client(app):
    """An HTTP client bound to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_headers(client):
    """Register and log in a user, returning its Bearer header."""
    await client.post(
        "/auth/register",
        json={"email": "chatter@example.com", "password": "secret123"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "chatter@example.com", "password": "secret123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
