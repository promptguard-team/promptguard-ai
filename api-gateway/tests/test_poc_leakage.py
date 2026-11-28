"""PoC LLM06 (sensitive data leakage) against the gateway's response rules.

Scenario from the attack taxonomy: the LLM reveals a secret in its reply. The
stubbed provider returns each leak; the gateway must replace the reply, audit
it as blocked_response with the rule name, and never hand the value back.

The rules inspect normalized text, so spaced-out, hyphen-grouped, line-split
and zero-width-padded secrets are caught too. Forms they still miss (base64,
a digit-padded or dotted PESEL) are strict xfails: they document the gap in the
PoC report and turn into failures the day a rule change closes them.
"""

import base64

import httpx
import pytest

from app.models import AuditAction
from tests.helpers import audit_events, override_llm

AWS_KEY = "AKIAIOSFODNN7EXAMPLE"  # pragma: allowlist secret
OPENAI_KEY = "sk-proj-Ab3dEf6hIj9kLm2nOp5qRs8tUv1wXy4z"  # pragma: allowlist secret
PRIVATE_KEY = (
    "-----BEGIN RSA PRIVATE KEY-----\n"  # pragma: allowlist secret
    "MIIEowIBAAKCAQEA\n"
    "-----END RSA PRIVATE KEY-----"
)
PESEL = "44051401359"

DETECTED = [
    pytest.param(f"Your key is {AWS_KEY}.", "aws_access_key", id="aws-plain"),
    pytest.param(AWS_KEY.lower(), "aws_access_key", id="aws-lowercase"),
    pytest.param(f"key{AWS_KEY}x", "aws_access_key", id="aws-glued"),
    pytest.param(f"Use {OPENAI_KEY} here.", "openai_api_key", id="openai-plain"),
    pytest.param(f"token:{OPENAI_KEY}", "openai_api_key", id="openai-glued"),
    pytest.param(PRIVATE_KEY, "private_key_block", id="private-key-rsa"),
    pytest.param(
        "-----BEGIN OPENSSH PRIVATE KEY-----",  # pragma: allowlist secret
        "private_key_block",
        id="private-key-openssh",
    ),
    pytest.param(PRIVATE_KEY.lower(), "private_key_block", id="private-key-lower"),
    pytest.param(f"PESEL klienta: {PESEL}", "pesel", id="pesel-plain"),
    pytest.param("PESEL: 440514-01359", "pesel", id="pesel-hyphen"),
    pytest.param("PESEL: 440514 01359", "pesel", id="pesel-space"),
    pytest.param(f"{PESEL}x", "pesel", id="pesel-glued-letter"),
    # Closed by input normalization (previously known gaps).
    pytest.param(" ".join(AWS_KEY), "aws_access_key", id="aws-spaced"),
    pytest.param(
        "-".join(AWS_KEY[i : i + 4] for i in range(0, 20, 4)),
        "aws_access_key",
        id="aws-hyphenated",
    ),
    pytest.param(
        AWS_KEY[:10] + "\n" + AWS_KEY[10:], "aws_access_key", id="aws-split-lines"
    ),
    pytest.param("​".join(AWS_KEY), "aws_access_key", id="aws-zero-width"),
    pytest.param(" ".join(OPENAI_KEY), "openai_api_key", id="openai-spaced"),
    pytest.param(" ".join(PESEL), "pesel", id="pesel-spaced"),
]

KNOWN_GAPS = [
    pytest.param(base64.b64encode(AWS_KEY.encode()).decode(), id="aws-base64"),
    pytest.param("0" + PESEL, id="pesel-digit-padded"),
    pytest.param("440.514.013.59", id="pesel-dotted"),
]


def _replying(content: str):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": content}}]}
        )

    return handler


async def _ask(app, client, headers, leak: str) -> httpx.Response:
    override_llm(app, _replying(f"Sure, here you go: {leak}"))
    return await client.post(
        "/chat", json={"prompt": "Show me the deployment config"}, headers=headers
    )


@pytest.mark.parametrize(("leak", "rule"), DETECTED)
async def test_leak_in_the_reply_is_blocked_and_audited(
    app, client, auth_headers, leak, rule
):
    resp = await _ask(app, client, auth_headers, leak)

    assert resp.status_code == 200
    body = resp.json()
    assert body["blocked"] is True
    assert leak not in body["response"]
    events = await audit_events(app)
    assert [event.action for event in events] == [AuditAction.blocked_response]
    assert events[0].rule == rule


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="known gap: no decoding, and PESEL digit groups are never joined",
)
@pytest.mark.parametrize("leak", KNOWN_GAPS)
async def test_obfuscated_leak_in_the_reply_is_blocked(app, client, auth_headers, leak):
    resp = await _ask(app, client, auth_headers, leak)

    assert resp.json()["blocked"] is True
