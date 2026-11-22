"""Bucketing for GET /audit/timeseries.

The database groups events by UTC hour; this module folds those hourly counts
into the requested buckets and zero-fills the range. It does no I/O, so the
calendar rules (Warsaw midnight, 23- and 25-hour DST days) are tested directly.
"""

import enum
from collections.abc import Iterable
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import AuditAction

# The CISO dashboard reports calendar days in this zone (see time_window).
DASHBOARD_TZ = ZoneInfo("Europe/Warsaw")


class Bucket(str, enum.Enum):
    """Width of one timeseries point."""

    hour = "hour"
    day = "day"


# Caps keep the hourly GROUP BY small: at most 92 * 24 hours * 4 actions rows.
MAX_WINDOW = {Bucket.hour: timedelta(days=7), Bucket.day: timedelta(days=92)}


def bucket_floor(moment: datetime, bucket: Bucket) -> datetime:
    """Return the start of the bucket containing the aware `moment`.

    Hour buckets are UTC hours (Warsaw offsets are whole hours, so they are
    local hours too); day buckets start at Warsaw midnight.
    """
    if bucket is Bucket.hour:
        return moment.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
    local_date = moment.astimezone(DASHBOARD_TZ).date()
    return datetime.combine(local_date, time.min, tzinfo=DASHBOARD_TZ)


def _next_start(start: datetime, bucket: Bucket) -> datetime:
    if bucket is Bucket.hour:
        return start + timedelta(hours=1)
    # Calendar arithmetic, not +24h: DST days are 23 or 25 hours long.
    following = start.date() + timedelta(days=1)
    return datetime.combine(following, time.min, tzinfo=DASHBOARD_TZ)


def bucket_starts(start: datetime, end: datetime, bucket: Bucket) -> list[datetime]:
    """Return the start of every bucket overlapping the window [start, end)."""
    starts = []
    current = bucket_floor(start, bucket)
    while current < end:
        starts.append(current)
        current = _next_start(current, bucket)
    return starts


def fold_hours(
    hourly: Iterable[tuple[datetime, AuditAction, int]],
    starts: list[datetime],
    bucket: Bucket,
) -> list[tuple[datetime, dict[str, int]]]:
    """Sum (utc_hour, action, count) rows into the buckets in `starts`.

    Every bucket and every action is present, zero when nothing happened.
    """
    totals = {start: {action.value: 0 for action in AuditAction} for start in starts}
    for hour, action, count in hourly:
        key = bucket_floor(hour, bucket)
        if key in totals:
            totals[key][action.value] += count
    return list(totals.items())
