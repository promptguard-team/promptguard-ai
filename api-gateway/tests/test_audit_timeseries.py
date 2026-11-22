from datetime import datetime, timedelta, timezone

import pytest

from app.models import AuditAction
from tests.audit_helpers import add_event, user_id_of

UTC = timezone.utc
ZERO = {action.value: 0 for action in AuditAction}


def counts(**overrides: int) -> dict[str, int]:
    return {**ZERO, **overrides}


@pytest.fixture
async def chatter(app, auth_headers):
    return await user_id_of(app, "chatter@example.com")


async def _series(client, headers, **params):
    resp = await client.get("/audit/timeseries", params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _window(start: str, end: str, bucket: str) -> dict[str, str]:
    return {"from": start, "to": end, "bucket": bucket}


async def test_requires_a_token(client):
    resp = await client.get(
        "/audit/timeseries",
        params=_window("2026-11-20T10:00:00Z", "2026-11-20T12:00:00Z", "hour"),
    )

    assert resp.status_code == 401


async def test_is_forbidden_to_a_chat_user(client, auth_headers):
    resp = await client.get(
        "/audit/timeseries",
        params=_window("2026-11-20T10:00:00Z", "2026-11-20T12:00:00Z", "hour"),
        headers=auth_headers,
    )

    assert resp.status_code == 403


async def test_hourly_buckets_are_zero_filled(app, client, chatter, ciso_headers):
    base = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    await add_event(app, user_id=chatter, created_at=base + timedelta(minutes=5))
    await add_event(
        app,
        user_id=chatter,
        created_at=base + timedelta(hours=2, minutes=59),
        action=AuditAction.blocked_prompt,
    )

    body = await _series(
        client,
        ciso_headers,
        **_window("2026-11-20T10:00:00Z", "2026-11-20T13:00:00Z", "hour"),
    )

    assert body == {
        "bucket": "hour",
        "points": [
            {"start": "2026-11-20T10:00:00Z", "by_action": counts(allowed=1)},
            {"start": "2026-11-20T11:00:00Z", "by_action": counts()},
            {"start": "2026-11-20T12:00:00Z", "by_action": counts(blocked_prompt=1)},
        ],
    }


async def test_daily_buckets_start_at_warsaw_midnight(
    app, client, chatter, ciso_headers
):
    # 22:30 UTC is 23:30 on Nov 19 in Warsaw; 23:30 UTC is already Nov 20.
    for hour in (22, 23):
        await add_event(
            app,
            user_id=chatter,
            created_at=datetime(2026, 11, 19, hour, 30, tzinfo=UTC),
        )

    body = await _series(
        client,
        ciso_headers,
        **_window("2026-11-18T23:00:00Z", "2026-11-20T23:00:00Z", "day"),
    )

    assert body["points"] == [
        {"start": "2026-11-19T00:00:00+01:00", "by_action": counts(allowed=1)},
        {"start": "2026-11-20T00:00:00+01:00", "by_action": counts(allowed=1)},
    ]


async def test_the_dst_end_day_spans_25_hours(app, client, chatter, ciso_headers):
    # On 2026-10-25 Warsaw falls back from UTC+2 to UTC+1: the local day runs
    # from 22:00 UTC on Oct 24 to 23:00 UTC on Oct 25.
    for moment in (
        datetime(2026, 10, 24, 22, 0, tzinfo=UTC),
        datetime(2026, 10, 25, 22, 59, tzinfo=UTC),
        datetime(2026, 10, 25, 23, 0, tzinfo=UTC),
    ):
        await add_event(app, user_id=chatter, created_at=moment)

    body = await _series(
        client,
        ciso_headers,
        **_window("2026-10-24T22:00:00Z", "2026-10-26T23:00:00Z", "day"),
    )

    assert body["points"] == [
        {"start": "2026-10-25T00:00:00+02:00", "by_action": counts(allowed=2)},
        {"start": "2026-10-26T00:00:00+01:00", "by_action": counts(allowed=1)},
    ]


async def test_events_outside_the_window_are_excluded_from_partial_buckets(
    app, client, chatter, ciso_headers
):
    for minute in (10, 40):
        await add_event(
            app,
            user_id=chatter,
            created_at=datetime(2026, 11, 20, 10, minute, tzinfo=UTC),
        )

    body = await _series(
        client,
        ciso_headers,
        **_window("2026-11-20T10:30:00Z", "2026-11-20T11:30:00Z", "hour"),
    )

    assert body["points"] == [
        {"start": "2026-11-20T10:00:00Z", "by_action": counts(allowed=1)},
        {"start": "2026-11-20T11:00:00Z", "by_action": counts()},
    ]


async def test_a_full_week_of_hours_is_allowed(client, ciso_headers):
    body = await _series(
        client,
        ciso_headers,
        **_window("2026-11-01T00:00:00Z", "2026-11-08T00:00:00Z", "hour"),
    )

    assert len(body["points"]) == 7 * 24


@pytest.mark.parametrize(
    "params",
    [
        {"bucket": "hour"},
        {"from": "2026-11-20T10:00:00Z", "bucket": "hour"},
        {"to": "2026-11-20T10:00:00Z", "bucket": "hour"},
        _window("2026-11-20T10:00:00", "2026-11-20T12:00:00", "hour"),
        _window("2026-11-20T12:00:00Z", "2026-11-20T10:00:00Z", "hour"),
        _window("2026-11-01T00:00:00Z", "2026-11-08T00:00:01Z", "hour"),
        _window("2026-01-01T00:00:00Z", "2026-04-04T00:00:00Z", "day"),
        _window("2026-11-20T10:00:00Z", "2026-11-20T12:00:00Z", "week"),
        {"from": "2026-11-20T10:00:00Z", "to": "2026-11-20T12:00:00Z"},
    ],
)
async def test_invalid_requests_are_rejected(client, ciso_headers, params):
    resp = await client.get("/audit/timeseries", params=params, headers=ciso_headers)

    assert resp.status_code == 422


async def test_a_full_92_days_of_daily_buckets_is_allowed(client, ciso_headers):
    body = await _series(
        client,
        ciso_headers,
        **_window("2026-01-01T00:00:00Z", "2026-04-03T00:00:00Z", "day"),
    )

    assert 92 <= len(body["points"]) <= 93


def test_the_postgres_query_groups_by_the_same_inline_expression():
    from sqlalchemy.dialects import postgresql

    from app.routers.audit import TimeWindow, _timeseries_query

    window = TimeWindow(
        start=datetime(2026, 11, 20, 10, tzinfo=UTC),
        end=datetime(2026, 11, 20, 12, tzinfo=UTC),
    )

    sql = str(
        _timeseries_query("postgresql", window).compile(dialect=postgresql.dialect())
    )

    expr = "date_trunc('hour', timezone('UTC', audit_events.created_at))"
    group_by = sql.split("GROUP BY")[1]
    assert expr in sql.split("GROUP BY")[0]
    assert expr in group_by
