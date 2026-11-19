"""Prometheus exposition for the gateway.

Values are read straight from the process-wide registry and compared as
deltas, so test order and the number of apps built in this process do not
matter.
"""

import httpx
from httpx import ASGITransport, AsyncClient
from prometheus_client import REGISTRY

from app.main import create_app
from tests.helpers import override_classifier, override_llm, scoring

_FAKE_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"  # pragma: allowlist secret

DECISIONS = "promptguard_chat_decisions_total"
FLAGGED = "promptguard_chat_flagged_total"


def sample(name: str, labels: dict[str, str] | None = None) -> float:
    """Current value of one series, or 0.0 if it has never been observed."""
    value = REGISTRY.get_sample_value(name, labels or {})
    return 0.0 if value is None else value


async def test_metrics_endpoint_is_public_and_in_prometheus_format(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "# HELP" in resp.text
    assert "http_requests_total" in resp.text


async def test_metrics_endpoint_is_hidden_from_openapi(client):
    resp = await client.get("/openapi.json")
    assert "/metrics" not in resp.json()["paths"]


async def test_http_requests_are_counted_by_route_template(client):
    labels = {"handler": "/health", "method": "GET", "status": "2xx"}
    before = sample("http_requests_total", labels)
    await client.get("/health")
    assert sample("http_requests_total", labels) == before + 1


async def test_every_app_in_the_process_is_instrumented():
    # The test suite (and app.main at import) builds many apps per process; a
    # regression here leaves every app after the first silently unmeasured.
    labels = {"handler": "/health", "method": "GET", "status": "2xx"}
    for _ in range(2):
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            before = sample("http_requests_total", labels)
            await c.get("/health")
            assert sample("http_requests_total", labels) == before + 1


def decisions_snapshot() -> dict[tuple[str, str], float]:
    """Every (action, ml_status) series currently in the registry."""
    actions = ("allowed", "blocked_prompt", "blocked_response", "provider_error")
    statuses = ("skipped", "ok", "unavailable")
    return {
        (a, s): sample(DECISIONS, {"action": a, "ml_status": s})
        for a in actions
        for s in statuses
    }


def assert_only_grew(before: dict, after: dict, key: tuple[str, str]) -> None:
    for k in before:
        expected = before[k] + 1 if k == key else before[k]
        assert after[k] == expected, f"series {k}: {before[k]} -> {after[k]}"


async def test_allowed_chat_counts_allowed_ok(client, auth_headers):
    before = decisions_snapshot()
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 200
    assert_only_grew(before, decisions_snapshot(), ("allowed", "ok"))


async def test_rule_block_counts_blocked_prompt_skipped(client, auth_headers):
    before = decisions_snapshot()
    resp = await client.post(
        "/chat", json={"prompt": f"use {_FAKE_AWS_KEY}"}, headers=auth_headers
    )
    assert resp.status_code == 403
    assert_only_grew(before, decisions_snapshot(), ("blocked_prompt", "skipped"))


async def test_ml_block_counts_blocked_prompt_ok(app, client, auth_headers):
    override_classifier(app, scoring(0.99))
    before = decisions_snapshot()
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 403
    assert_only_grew(before, decisions_snapshot(), ("blocked_prompt", "ok"))


async def test_classifier_outage_counts_allowed_unavailable(app, client, auth_headers):
    override_classifier(app, lambda request: httpx.Response(500))
    before = decisions_snapshot()
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 200
    assert_only_grew(before, decisions_snapshot(), ("allowed", "unavailable"))


async def test_provider_error_counts_provider_error_ok(app, client, auth_headers):
    override_llm(app, lambda request: httpx.Response(503))
    before = decisions_snapshot()
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 502
    assert_only_grew(before, decisions_snapshot(), ("provider_error", "ok"))


async def test_blocked_response_counts_blocked_response_ok(app, client, auth_headers):
    def leaking_llm(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": f"key {_FAKE_AWS_KEY}"}}]},
        )

    override_llm(app, leaking_llm)
    before = decisions_snapshot()
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["blocked"] is True
    assert_only_grew(before, decisions_snapshot(), ("blocked_response", "ok"))


async def test_review_threshold_counts_flagged(app, client, auth_headers):
    override_classifier(app, scoring(0.75))  # between review 0.60 and block 0.90
    before = sample(FLAGGED)
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 200
    assert sample(FLAGGED) == before + 1


async def test_clean_prompt_is_not_flagged(client, auth_headers):
    before = sample(FLAGGED)
    await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert sample(FLAGGED) == before
