import httpx
import pytest_asyncio
from sqlalchemy import select

from app.llm import LLMClient
from app.models import AuditAction, AuditEvent

_FAKE_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"  # pragma: allowlist secret


@pytest_asyncio.fixture
async def auth_headers(client):
    await client.post(
        "/auth/register",
        json={"email": "chatter@example.com", "password": "secret123"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "chatter@example.com", "password": "secret123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _audit_events(app):
    maker = app.state.sessionmaker
    async with maker() as session:
        result = await session.execute(select(AuditEvent))
        return list(result.scalars())


def _override_llm(app, handler):
    app.state.llm_client = LLMClient(
        api_base="https://llm.test/v1",
        api_key="test-key",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )


async def test_chat_requires_auth(app, client):
    resp = await client.post("/chat", json={"prompt": "hello"})
    assert resp.status_code == 401
    events = await _audit_events(app)
    assert len(events) == 0


async def test_chat_rejects_empty_prompt(app, client, auth_headers):
    resp = await client.post("/chat", json={"prompt": ""}, headers=auth_headers)
    assert resp.status_code == 422
    events = await _audit_events(app)
    assert len(events) == 0


async def test_chat_rejects_oversized_prompt(app, client, auth_headers):
    resp = await client.post(
        "/chat", json={"prompt": "a" * 32001}, headers=auth_headers
    )
    assert resp.status_code == 422
    # The over-long prompt is exactly what this product expects to carry
    # secrets, so it must not come back verbatim, un-inspected and
    # un-audited, in the validation-error body.
    assert "a" * 100 not in resp.text
    events = await _audit_events(app)
    assert len(events) == 0


async def test_chat_returns_llm_reply_and_audits(app, client, auth_headers):
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"response": "mock reply", "blocked": False}
    events = await _audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.allowed
    assert events[0].prompt == "hello"
    assert events[0].response == "mock reply"


async def test_chat_blocks_prompt_with_secret(app, client, auth_headers):
    resp = await client.post(
        "/chat",
        json={"prompt": f"use {_FAKE_AWS_KEY} please"},
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert "aws_access_key" not in resp.text
    events = await _audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.blocked_prompt
    assert events[0].rule == "aws_access_key"


async def test_chat_blocks_leaky_response(app, client, auth_headers):
    def leaky(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": f"sure: {_FAKE_AWS_KEY}"}}]},
        )

    _override_llm(app, leaky)
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocked"] is True
    assert "AKIA" not in data["response"]
    assert "aws_access_key" not in resp.text
    events = await _audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.blocked_response
    assert events[0].rule == "aws_access_key"
    assert events[0].response == f"sure: {_FAKE_AWS_KEY}"


async def test_chat_returns_502_when_provider_down(app, client, auth_headers):
    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    _override_llm(app, down)
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 502
    events = await _audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.allowed
    assert events[0].prompt == "hello"
    assert events[0].response is None
    assert events[0].rule is None


async def test_chat_returns_502_when_provider_sends_null_content(
    app, client, auth_headers
):
    def null_content(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": None}}]})

    _override_llm(app, null_content)
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 502
    events = await _audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.allowed
    assert events[0].prompt == "hello"
    assert events[0].response is None
    assert events[0].rule is None
