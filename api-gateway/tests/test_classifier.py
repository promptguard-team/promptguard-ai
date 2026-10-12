import httpx
import pytest

from app.classifier import ClassifierClient, ClassifierError
from app.models.audit import MAX_ML_LABEL_CHARS, MAX_ML_MODEL_VERSION_CHARS


def _client(handler, **kwargs):
    return ClassifierClient(
        base_url="http://ml.test",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


async def test_classify_returns_a_verdict():
    def ok(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/classify"
        return httpx.Response(
            200,
            json={"label": "injection", "score": 0.93, "model_version": "stub-0"},
        )

    verdict = await _client(ok).classify("hello")
    assert verdict.label == "injection"
    assert verdict.score == 0.93
    assert verdict.model_version == "stub-0"


async def test_classify_sends_the_text_in_the_body():
    seen = {}

    def capture(request: httpx.Request) -> httpx.Response:
        seen["content"] = request.content
        return httpx.Response(
            200, json={"label": "clean", "score": 0.0, "model_version": "stub-0"}
        )

    await _client(capture).classify("a prompt")
    assert b"a prompt" in seen["content"]


@pytest.mark.parametrize(
    "payload",
    [
        {"label": "clean", "score": 1.5, "model_version": "s"},
        {"label": "clean", "score": -0.1, "model_version": "s"},
        {"label": "clean", "score": "high", "model_version": "s"},
        {"label": "clean", "score": True, "model_version": "s"},
        {"label": 7, "score": 0.5, "model_version": "s"},
        {"label": "clean", "score": 0.5},
        {"score": 0.5, "model_version": "s"},
        {},
    ],
)
async def test_classify_rejects_malformed_payloads(payload):
    # None of these may become score=0.0, which would turn a broken
    # classifier into "everything looks clean".
    def bad(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with pytest.raises(ClassifierError):
        await _client(bad).classify("hello")


async def test_classify_rejects_non_json_body():
    def html(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>gateway timeout</html>")

    with pytest.raises(ClassifierError):
        await _client(html).classify("hello")


async def test_classify_raises_on_http_error_status():
    def boom(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "nope"})

    with pytest.raises(ClassifierError):
        await _client(boom).classify("hello")


async def test_classify_raises_on_transport_failure():
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(ClassifierError):
        await _client(refused).classify("hello")


async def test_classify_accepts_integer_scores():
    def integral(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"label": "clean", "score": 0, "model_version": "s"}
        )

    verdict = await _client(integral).classify("hello")
    assert verdict.score == 0.0


def _payload(label="clean", version="stub-0"):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"label": label, "score": 0.5, "model_version": version}
        )

    return handler


@pytest.mark.parametrize(
    "label,version",
    [
        ("x" * (MAX_ML_LABEL_CHARS + 1), "stub-0"),
        ("clean", "v" * (MAX_ML_MODEL_VERSION_CHARS + 1)),
    ],
)
async def test_classify_rejects_strings_wider_than_the_audit_columns(label, version):
    # audit_events.ml_label is String(32) and ml_model_version String(64). On
    # PostgreSQL an over-long value raises DataError inside the audit write,
    # which on the allowed path runs only after the prompt has already been
    # sent to the provider. Rejecting here routes it into fail-open instead.
    with pytest.raises(ClassifierError):
        await _client(_payload(label, version)).classify("hello")


async def test_classify_accepts_strings_exactly_at_the_column_width():
    # The limits are inclusive: a label of exactly 32 characters fits the
    # column, so rejecting it would throw away a usable verdict.
    label = "x" * MAX_ML_LABEL_CHARS
    version = "v" * MAX_ML_MODEL_VERSION_CHARS
    verdict = await _client(_payload(label, version)).classify("hello")
    assert verdict.label == label
    assert verdict.model_version == version
