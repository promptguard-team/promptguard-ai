"""Shared test helpers for the /chat suites."""

import httpx
from sqlalchemy import select

from app.classifier import ClassifierClient
from app.llm import LLMClient
from app.models import AuditEvent


async def audit_events(app):
    """Every audit row written so far."""
    maker = app.state.sessionmaker
    async with maker() as session:
        result = await session.execute(select(AuditEvent))
        return list(result.scalars())


def override_llm(app, handler):
    """Replace the LLM client with one backed by `handler`."""
    app.state.llm_client = LLMClient(
        api_base="https://llm.test/v1",
        api_key="test-key",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )


def override_classifier(app, handler):
    """Replace the classifier client with one backed by `handler`."""
    app.state.classifier_client = ClassifierClient(
        base_url="http://ml.test", transport=httpx.MockTransport(handler)
    )


def scoring(score, label="injection", version="test-model-0"):
    """A classifier handler that always returns `score`."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"label": label, "score": score, "model_version": version}
        )

    return handler
