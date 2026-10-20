import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models import AuditAction, MLStatus
from tests.audit_helpers import add_event, user_id_of

TEN_UTC = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
async def chatter(app, auth_headers):
    return await user_id_of(app, "chatter@example.com")


def _ids(resp):
    assert resp.status_code == 200, resp.text
    return [uuid.UUID(item["id"]) for item in resp.json()["items"]]


async def _seed_hours(app, user_id):
    """Events at 10:00, 11:00 and 12:00 UTC, returned in that order."""
    return [
        await add_event(app, user_id=user_id, created_at=TEN_UTC + timedelta(hours=h))
        for h in range(3)
    ]


async def test_list_is_forbidden_to_a_chat_user(client, auth_headers):
    resp = await client.get("/audit/events", headers=auth_headers)

    assert resp.status_code == 403


async def test_list_items_carry_no_text(app, client, chatter, ciso_headers):
    await add_event(
        app,
        user_id=chatter,
        created_at=TEN_UTC,
        prompt="secret plan",
        response="reply",
    )

    resp = await client.get("/audit/events", headers=ciso_headers)

    item = resp.json()["items"][0]
    assert "prompt" not in item
    assert "response" not in item
    assert "secret plan" not in resp.text


async def test_list_is_newest_first_and_carries_user_email(
    app, client, chatter, ciso_headers
):
    ten, eleven, twelve = await _seed_hours(app, chatter)

    resp = await client.get("/audit/events", headers=ciso_headers)

    assert _ids(resp) == [twelve, eleven, ten]
    assert {item["user_email"] for item in resp.json()["items"]} == {
        "chatter@example.com"
    }


async def test_equal_timestamps_order_by_id_desc_and_page_each_row_once(
    app, client, chatter, ciso_headers
):
    # Inserted in an order that is neither ascending nor descending: SQLite
    # returns tied rows in insertion order, or its reverse when it walks the
    # created_at index backwards, so sorted insertion would pass without the
    # id tiebreak.
    for n in (3, 1, 5, 2, 4):
        await add_event(app, user_id=chatter, created_at=TEN_UTC, id=uuid.UUID(int=n))

    seen = []
    for offset in (0, 2, 4):
        resp = await client.get(
            "/audit/events",
            params={"limit": 2, "offset": offset},
            headers=ciso_headers,
        )
        seen += _ids(resp)

    assert seen == [uuid.UUID(int=n) for n in (5, 4, 3, 2, 1)]


async def test_total_ignores_limit_and_offset(app, client, chatter, ciso_headers):
    for minute in range(7):
        await add_event(
            app, user_id=chatter, created_at=TEN_UTC + timedelta(minutes=minute)
        )

    resp = await client.get(
        "/audit/events", params={"limit": 3, "offset": 3}, headers=ciso_headers
    )

    body = resp.json()
    assert len(body["items"]) == 3
    assert body["total"] == 7
    assert (body["limit"], body["offset"]) == (3, 3)


async def test_offset_past_end_is_empty_with_true_total(
    app, client, chatter, ciso_headers
):
    for minute in range(7):
        await add_event(
            app, user_id=chatter, created_at=TEN_UTC + timedelta(minutes=minute)
        )

    resp = await client.get(
        "/audit/events", params={"offset": 50}, headers=ciso_headers
    )

    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 7


async def test_repeated_action_is_or(app, client, chatter, ciso_headers):
    await add_event(app, user_id=chatter, created_at=TEN_UTC)
    blocked_prompt = await add_event(
        app, user_id=chatter, created_at=TEN_UTC, action=AuditAction.blocked_prompt
    )
    blocked_response = await add_event(
        app, user_id=chatter, created_at=TEN_UTC, action=AuditAction.blocked_response
    )

    resp = await client.get(
        "/audit/events",
        params=[("action", "blocked_prompt"), ("action", "blocked_response")],
        headers=ciso_headers,
    )

    assert set(_ids(resp)) == {blocked_prompt, blocked_response}
    assert resp.json()["total"] == 2


async def test_filters_flagged_ml_status_and_user(app, client, chatter, ciso_headers):
    ciso = await user_id_of(app, "ciso@example.com")
    plain = await add_event(app, user_id=chatter, created_at=TEN_UTC)
    flagged = await add_event(app, user_id=chatter, created_at=TEN_UTC, flagged=True)
    degraded = await add_event(
        app, user_id=chatter, created_at=TEN_UTC, ml_status=MLStatus.unavailable
    )
    by_ciso = await add_event(app, user_id=ciso, created_at=TEN_UTC)

    async def ids(**params):
        resp = await client.get("/audit/events", params=params, headers=ciso_headers)
        return set(_ids(resp))

    assert await ids(flagged="true") == {flagged}
    assert await ids(flagged="false") == {plain, degraded, by_ciso}
    assert await ids(ml_status="unavailable") == {degraded}
    assert await ids(user_id=str(ciso)) == {by_ciso}


async def test_from_inclusive_to_exclusive(app, client, chatter, ciso_headers):
    ten, eleven, _ = await _seed_hours(app, chatter)

    resp = await client.get(
        "/audit/events",
        params={"from": "2026-10-20T10:00:00Z", "to": "2026-10-20T12:00:00Z"},
        headers=ciso_headers,
    )

    assert _ids(resp) == [eleven, ten]


async def test_offset_window_equals_utc_window(app, client, chatter, ciso_headers):
    ten, eleven, _ = await _seed_hours(app, chatter)

    resp = await client.get(
        "/audit/events",
        params={
            "from": "2026-10-20T12:00:00+02:00",
            "to": "2026-10-20T14:00:00+02:00",
        },
        headers=ciso_headers,
    )

    assert _ids(resp) == [eleven, ten]


async def test_unencoded_plus_in_from_is_422(client, ciso_headers):
    # A raw `+` in a query string decodes to a space. It must fail loudly,
    # never select a silently shifted window.
    resp = await client.get(
        "/audit/events?from=2026-10-20T12:00:00+02:00", headers=ciso_headers
    )

    assert resp.status_code == 422


async def test_naive_datetime_is_422(client, ciso_headers):
    resp = await client.get(
        "/audit/events", params={"from": "2026-10-20T10:00:00"}, headers=ciso_headers
    )

    assert resp.status_code == 422


async def test_from_not_before_to_is_422(client, ciso_headers):
    resp = await client.get(
        "/audit/events",
        params={"from": "2026-10-20T10:00:00Z", "to": "2026-10-20T10:00:00Z"},
        headers=ciso_headers,
    )

    assert resp.status_code == 422
    assert "earlier" in resp.text


@pytest.mark.parametrize(("limit", "status"), [(0, 422), (201, 422), (200, 200)])
async def test_limit_bounds(client, ciso_headers, limit, status):
    resp = await client.get(
        "/audit/events", params={"limit": limit}, headers=ciso_headers
    )

    assert resp.status_code == status
