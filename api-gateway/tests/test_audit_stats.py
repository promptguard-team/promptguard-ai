from datetime import datetime, timedelta, timezone

import pytest

from app.models import AuditAction, MLStatus
from tests.audit_helpers import add_event, user_id_of

TEN_UTC = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
EMPTY_BY_ACTION = {action.value: 0 for action in AuditAction}


@pytest.fixture
async def chatter(app, auth_headers):
    return await user_id_of(app, "chatter@example.com")


async def _stats(client, headers, **params):
    resp = await client.get("/audit/stats", params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _seed_hours(app, user_id):
    for hours in range(3):
        await add_event(
            app, user_id=user_id, created_at=TEN_UTC + timedelta(hours=hours)
        )


async def test_stats_is_forbidden_to_a_chat_user(client, auth_headers):
    resp = await client.get("/audit/stats", headers=auth_headers)

    assert resp.status_code == 403


async def test_stats_on_empty_table(client, ciso_headers):
    assert await _stats(client, ciso_headers) == {
        "total": 0,
        "by_action": EMPTY_BY_ACTION,
        "flagged": 0,
        "ml_unavailable": 0,
    }


async def test_stats_counts(app, client, chatter, ciso_headers):
    await add_event(app, user_id=chatter, created_at=TEN_UTC)
    await add_event(app, user_id=chatter, created_at=TEN_UTC, flagged=True)
    await add_event(
        app, user_id=chatter, created_at=TEN_UTC, ml_status=MLStatus.unavailable
    )
    for _ in range(2):
        await add_event(
            app, user_id=chatter, created_at=TEN_UTC, action=AuditAction.blocked_prompt
        )
    await add_event(
        app, user_id=chatter, created_at=TEN_UTC, action=AuditAction.provider_error
    )

    assert await _stats(client, ciso_headers) == {
        "total": 6,
        "by_action": {
            **EMPTY_BY_ACTION,
            "allowed": 3,
            "blocked_prompt": 2,
            "provider_error": 1,
        },
        "flagged": 1,
        "ml_unavailable": 1,
    }


async def test_stats_respects_window(app, client, chatter, ciso_headers):
    await _seed_hours(app, chatter)

    stats = await _stats(
        client,
        ciso_headers,
        **{"from": "2026-10-20T10:00:00Z", "to": "2026-10-20T12:00:00Z"},
    )

    assert stats["total"] == 2
    assert stats["by_action"]["allowed"] == 2


async def test_stats_open_ended_window(app, client, chatter, ciso_headers):
    await _seed_hours(app, chatter)

    since = await _stats(client, ciso_headers, **{"from": "2026-10-20T11:00:00Z"})
    until = await _stats(client, ciso_headers, to="2026-10-20T11:00:00Z")

    assert since["total"] == 2
    assert until["total"] == 1


async def test_stats_naive_datetime_is_422(client, ciso_headers):
    resp = await client.get(
        "/audit/stats", params={"from": "2026-10-20T10:00:00"}, headers=ciso_headers
    )

    assert resp.status_code == 422


async def test_stats_window_applies_to_flagged_and_ml_unavailable(
    app, client, chatter, ciso_headers
):
    # Each counter has one event inside the window and one outside it, so a
    # query that drops the window from either counter is off by one.
    for hours in (0, 3):
        at = TEN_UTC + timedelta(hours=hours)
        await add_event(app, user_id=chatter, created_at=at, flagged=True)
        await add_event(
            app, user_id=chatter, created_at=at, ml_status=MLStatus.unavailable
        )

    stats = await _stats(
        client,
        ciso_headers,
        **{"from": "2026-10-20T10:00:00Z", "to": "2026-10-20T12:00:00Z"},
    )

    assert stats == {
        "total": 2,
        "by_action": {**EMPTY_BY_ACTION, "allowed": 2},
        "flagged": 1,
        "ml_unavailable": 1,
    }
