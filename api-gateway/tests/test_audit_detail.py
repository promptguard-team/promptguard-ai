import uuid
from datetime import datetime, timedelta, timezone

from app.cli import set_role
from app.models import AuditAction, UserRole
from tests.audit_helpers import add_event, user_id_of

TEN_UTC = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)


async def _seed(app, **fields):
    chatter = await user_id_of(app, "chatter@example.com")
    return await add_event(app, user_id=chatter, created_at=TEN_UTC, **fields)


async def test_detail_requires_a_token(client):
    resp = await client.get(f"/audit/events/{uuid.uuid4()}")

    assert resp.status_code == 401


async def test_detail_is_forbidden_to_a_chat_user(app, client, auth_headers):
    event_id = await _seed(app)

    resp = await client.get(f"/audit/events/{event_id}", headers=auth_headers)

    assert resp.status_code == 403


async def test_detail_returns_prompt_and_response(
    app, client, auth_headers, ciso_headers
):
    event_id = await _seed(app, prompt="secret plan", response="reply text")

    resp = await client.get(f"/audit/events/{event_id}", headers=ciso_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["prompt"] == "secret plan"
    assert body["response"] == "reply text"
    assert body["user_email"] == "chatter@example.com"
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.utcoffset() == timedelta(0)
    assert created_at == TEN_UTC


async def test_detail_of_provider_error_has_null_response(
    app, client, auth_headers, ciso_headers
):
    event_id = await _seed(app, action=AuditAction.provider_error)

    resp = await client.get(f"/audit/events/{event_id}", headers=ciso_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "provider_error"
    for field in ("response", "rule", "ml_score", "ml_label", "ml_model_version"):
        assert body[field] is None, field


async def test_detail_unknown_id_is_404(client, ciso_headers):
    resp = await client.get(f"/audit/events/{uuid.uuid4()}", headers=ciso_headers)

    assert resp.status_code == 404
    # A missing route is also a 404; the detail tells the two apart.
    assert resp.json()["detail"] == "audit event not found"


async def test_detail_malformed_id_is_422(client, ciso_headers):
    resp = await client.get("/audit/events/not-a-uuid", headers=ciso_headers)

    assert resp.status_code == 422


async def test_demoted_ciso_loses_access_with_the_same_token(
    app, client, auth_headers, ciso_headers
):
    event_id = await _seed(app)
    url = f"/audit/events/{event_id}"
    assert (await client.get(url, headers=ciso_headers)).status_code == 200

    await set_role(app.state.sessionmaker, "ciso@example.com", UserRole.chat_user)

    assert (await client.get(url, headers=ciso_headers)).status_code == 403
