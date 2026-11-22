from datetime import datetime, timedelta, timezone

from app.models import AuditAction
from app.timeseries import DASHBOARD_TZ, Bucket, bucket_floor, bucket_starts, fold_hours

UTC = timezone.utc


def test_hour_floor_truncates_to_the_utc_hour():
    moment = datetime(2026, 11, 20, 11, 59, 59, tzinfo=DASHBOARD_TZ)

    assert bucket_floor(moment, Bucket.hour) == datetime(2026, 11, 20, 10, tzinfo=UTC)


def test_day_floor_is_warsaw_midnight():
    # 23:30 UTC is 00:30 the next day in Warsaw (UTC+1 in winter).
    moment = datetime(2026, 11, 19, 23, 30, tzinfo=UTC)

    floor = bucket_floor(moment, Bucket.day)

    assert floor == datetime(2026, 11, 20, tzinfo=DASHBOARD_TZ)
    assert floor.utcoffset() == timedelta(hours=1)


def test_hour_starts_cover_a_partial_first_bucket():
    starts = bucket_starts(
        datetime(2026, 11, 20, 10, 30, tzinfo=UTC),
        datetime(2026, 11, 20, 12, 0, tzinfo=UTC),
        Bucket.hour,
    )

    assert starts == [
        datetime(2026, 11, 20, 10, tzinfo=UTC),
        datetime(2026, 11, 20, 11, tzinfo=UTC),
    ]


def test_day_starts_follow_the_calendar_across_dst_end():
    starts = bucket_starts(
        datetime(2026, 10, 24, 22, 0, tzinfo=UTC),
        datetime(2026, 10, 26, 23, 0, tzinfo=UTC),
        Bucket.day,
    )

    assert [s.isoformat() for s in starts] == [
        "2026-10-25T00:00:00+02:00",
        "2026-10-26T00:00:00+01:00",
    ]
    # Same-tzinfo subtraction is wall-clock; compare real elapsed time in UTC.
    assert starts[1].astimezone(UTC) - starts[0].astimezone(UTC) == timedelta(hours=25)


def test_fold_sums_hours_into_days_and_zero_fills():
    starts = bucket_starts(
        datetime(2026, 11, 18, 23, 0, tzinfo=UTC),
        datetime(2026, 11, 20, 23, 0, tzinfo=UTC),
        Bucket.day,
    )
    hourly = [
        (datetime(2026, 11, 19, 8, tzinfo=UTC), AuditAction.allowed, 2),
        (datetime(2026, 11, 19, 9, tzinfo=UTC), AuditAction.allowed, 1),
        (datetime(2026, 11, 19, 9, tzinfo=UTC), AuditAction.blocked_prompt, 4),
        # Outside every bucket: ignored rather than raising.
        (datetime(2026, 11, 25, 9, tzinfo=UTC), AuditAction.allowed, 7),
    ]

    points = fold_hours(hourly, starts, Bucket.day)

    zero = {action.value: 0 for action in AuditAction}
    assert points == [
        (starts[0], {**zero, "allowed": 3, "blocked_prompt": 4}),
        (starts[1], zero),
    ]


def test_the_dst_start_day_spans_23_hours():
    # Warsaw springs forward on 2026-03-29: that local day has only 23 hours.
    first = datetime(2026, 3, 28, 23, 0, tzinfo=UTC)
    end = datetime(2026, 3, 30, 22, 0, tzinfo=UTC)
    starts = bucket_starts(first, end, Bucket.day)
    hourly = [
        (first + timedelta(hours=offset), AuditAction.allowed, 1)
        for offset in range(47)
    ]

    points = fold_hours(hourly, starts, Bucket.day)

    assert starts[1].astimezone(UTC) - starts[0].astimezone(UTC) == timedelta(hours=23)
    assert [by_action["allowed"] for _, by_action in points] == [23, 24]
