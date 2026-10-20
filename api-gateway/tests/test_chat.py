import httpx
import pytest

from app.config import get_settings
from app.models import AuditAction, MLStatus
from app.models.audit import MAX_ML_LABEL_CHARS, MAX_ML_MODEL_VERSION_CHARS
from tests.helpers import (
    audit_events,
    counting_llm,
    override_classifier,
    override_llm,
    scoring,
)

_FAKE_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"  # pragma: allowlist secret


async def test_chat_requires_auth(app, client):
    resp = await client.post("/chat", json={"prompt": "hello"})
    assert resp.status_code == 401
    events = await audit_events(app)
    assert len(events) == 0


async def test_chat_rejects_empty_prompt(app, client, auth_headers):
    resp = await client.post("/chat", json={"prompt": ""}, headers=auth_headers)
    assert resp.status_code == 422
    events = await audit_events(app)
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
    events = await audit_events(app)
    assert len(events) == 0


async def test_chat_returns_llm_reply_and_audits(app, client, auth_headers):
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"response": "mock reply", "blocked": False}
    events = await audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.allowed
    assert events[0].prompt == "hello"
    assert events[0].response == "mock reply"


async def test_chat_blocks_prompt_with_secret(app, client, auth_headers):
    llm_calls = counting_llm(app)
    resp = await client.post(
        "/chat",
        json={"prompt": f"use {_FAKE_AWS_KEY} please"},
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert "aws_access_key" not in resp.text
    # The whole point of blocking is that the prompt never leaves. A 403
    # returned after forwarding would satisfy every other assertion here.
    assert llm_calls == []
    events = await audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.blocked_prompt
    assert events[0].rule == "aws_access_key"


async def test_chat_blocks_leaky_response(app, client, auth_headers):
    def leaky(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": f"sure: {_FAKE_AWS_KEY}"}}]},
        )

    override_llm(app, leaky)
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocked"] is True
    assert "AKIA" not in data["response"]
    assert "aws_access_key" not in resp.text
    events = await audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.blocked_response
    assert events[0].rule == "aws_access_key"
    assert events[0].response == f"sure: {_FAKE_AWS_KEY}"


async def test_chat_returns_502_when_provider_down(app, client, auth_headers):
    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    override_llm(app, down)
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 502
    events = await audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.provider_error
    assert events[0].prompt == "hello"
    assert events[0].response is None
    assert events[0].rule is None


async def test_chat_returns_502_when_provider_sends_null_content(
    app, client, auth_headers
):
    def null_content(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": None}}]})

    override_llm(app, null_content)
    resp = await client.post("/chat", json={"prompt": "hello"}, headers=auth_headers)
    assert resp.status_code == 502
    events = await audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.provider_error
    assert events[0].prompt == "hello"
    assert events[0].response is None
    assert events[0].rule is None


async def test_high_score_blocks_the_prompt(app, client, auth_headers):
    override_classifier(app, scoring(0.95))
    llm_calls = counting_llm(app)
    resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    assert resp.status_code == 403
    # As above: a refactor that scored and forwarded concurrently would still
    # return 403 and still write one audit row.
    assert llm_calls == []
    events = await audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.blocked_prompt
    assert events[0].rule is None
    assert events[0].ml_status == MLStatus.ok
    assert events[0].ml_score == 0.95
    assert events[0].ml_model_version == "test-model-0"


async def test_middle_band_is_allowed_and_flagged(app, client, auth_headers):
    override_classifier(app, scoring(0.70))
    resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    assert resp.status_code == 200
    events = await audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.allowed
    assert events[0].flagged is True
    assert events[0].ml_status == MLStatus.ok


async def test_low_score_is_allowed_and_not_flagged(app, client, auth_headers):
    override_classifier(app, scoring(0.05, label="clean"))
    resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    assert resp.status_code == 200
    events = await audit_events(app)
    assert events[0].flagged is False
    assert events[0].ml_status == MLStatus.ok


async def test_classifier_outage_fails_open_and_is_recorded(app, client, auth_headers):
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    override_classifier(app, refused)
    resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    assert resp.status_code == 200
    events = await audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.allowed
    assert events[0].ml_status == MLStatus.unavailable
    assert events[0].ml_score is None
    assert events[0].flagged is False


async def test_malformed_verdict_is_an_outage_not_a_clean_score(
    app, client, auth_headers
):
    def garbage(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"score": 1.5})

    override_classifier(app, garbage)
    resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    assert resp.status_code == 200
    events = await audit_events(app)
    assert events[0].ml_status == MLStatus.unavailable
    assert events[0].ml_score is None


async def test_rule_match_skips_the_classifier_entirely(app, client, auth_headers):
    calls = []

    def counting(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json={"label": "clean", "score": 0.0, "model_version": "x"}
        )

    override_classifier(app, counting)
    resp = await client.post(
        "/chat", json={"prompt": f"use {_FAKE_AWS_KEY}"}, headers=auth_headers
    )
    assert resp.status_code == 403
    assert calls == []
    events = await audit_events(app)
    assert events[0].ml_status == MLStatus.skipped
    assert events[0].rule == "aws_access_key"


async def test_flagged_prompt_with_leaky_response_records_both(
    app, client, auth_headers
):
    # The collision the two-axis design exists for: how the request ended and
    # what the model thought are independent facts.
    override_classifier(app, scoring(0.70))

    def leaky(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": f"sure: {_FAKE_AWS_KEY}"}}]}
        )

    override_llm(app, leaky)
    resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    assert resp.status_code == 200
    events = await audit_events(app)
    assert len(events) == 1
    assert events[0].action == AuditAction.blocked_response
    assert events[0].rule == "aws_access_key"
    assert events[0].flagged is True
    assert events[0].ml_score == 0.70


async def test_blocked_prompt_is_never_flagged(app, client, auth_headers):
    # flagged means "allowed but needs review". A blocked row is not awaiting
    # a decision, so it must not appear in the CISO review queue.
    override_classifier(app, scoring(0.99))
    await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    events = await audit_events(app)
    assert events[0].flagged is False


@pytest.mark.parametrize(
    "score,llm_content,prompt",
    [
        (0.95, "ok", "hi"),
        (0.70, "ok", "hi"),
        (0.05, "ok", "hi"),
        (0.05, _FAKE_AWS_KEY, "hi"),
        (0.05, "ok", f"use {_FAKE_AWS_KEY}"),
    ],
)
async def test_exactly_one_audit_row_per_request(
    app, client, auth_headers, score, llm_content, prompt
):
    override_classifier(app, scoring(score))

    def reply(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": llm_content}}]}
        )

    override_llm(app, reply)
    await client.post("/chat", json={"prompt": prompt}, headers=auth_headers)
    events = await audit_events(app)
    assert len(events) == 1


async def test_score_exactly_at_the_block_threshold_is_blocked(
    app, client, auth_headers
):
    # The thresholds are inclusive ("at or above"), and the decision boundary
    # is the one value the scenario scores (0.95/0.70/0.05) never touch:
    # turning either `>=` into `>` leaves all of them passing.
    assert get_settings().classifier_block_threshold == 0.90
    override_classifier(app, scoring(0.90))
    resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    assert resp.status_code == 403
    events = await audit_events(app)
    assert events[0].action == AuditAction.blocked_prompt
    assert events[0].ml_score == 0.90


async def test_score_exactly_at_the_review_threshold_is_allowed_and_flagged(
    app, client, auth_headers
):
    assert get_settings().classifier_review_threshold == 0.60
    override_classifier(app, scoring(0.60))
    resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    assert resp.status_code == 200
    events = await audit_events(app)
    assert events[0].action == AuditAction.allowed
    assert events[0].flagged is True


async def test_score_just_below_the_review_threshold_is_not_flagged(
    app, client, auth_headers
):
    # The negative half of the boundary: without it, `score >= 0` would also
    # satisfy the two cases above.
    override_classifier(app, scoring(0.5999))
    resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    assert resp.status_code == 200
    events = await audit_events(app)
    assert events[0].action == AuditAction.allowed
    assert events[0].flagged is False


@pytest.mark.parametrize(
    "label,version",
    [
        ("injection" * MAX_ML_LABEL_CHARS, "test-model-0"),
        ("injection", "v" * (MAX_ML_MODEL_VERSION_CHARS + 1)),
    ],
)
async def test_verdict_too_wide_for_the_audit_columns_fails_open(
    app, client, auth_headers, label, version
):
    # SQLite does not enforce VARCHAR width, so this test cannot observe the
    # DataError PostgreSQL would raise; what it pins is that such a verdict
    # never reaches the INSERT at all, and is recorded as an outage.
    override_classifier(app, scoring(0.95, label=label, version=version))
    resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    # 0.95 would have blocked; an unusable verdict must fail open instead of
    # being acted on.
    assert resp.status_code == 200
    events = await audit_events(app)
    assert len(events) == 1
    assert events[0].ml_status == MLStatus.unavailable
    assert events[0].ml_label is None
    assert events[0].ml_model_version is None


async def test_classifier_outage_is_logged_with_its_cause(
    app, client, auth_headers, caplog
):
    # Fail-open is otherwise invisible outside audit_events: a mistyped
    # CLASSIFIER_URL would disable Layer 2 indefinitely in silence.
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    override_classifier(app, refused)
    with caplog.at_level("WARNING", logger="app.routers.chat"):
        resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
    assert resp.status_code == 200
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert warnings, "the fail-open path logged nothing"
    assert "connection refused" in warnings[0].getMessage()
