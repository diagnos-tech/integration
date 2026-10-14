"""Dates the way the web app writes them: UTC ISO 8601 instants, optionally truncated to a precision.

Every date inside a sealed record (`birth_date`, `exam_date`) is stored as
the string JavaScript's `Date.toISOString()` produces,
`YYYY-MM-DDTHH:MM:SS.sssZ`, always in UTC. Writing the same shape keeps a
record the SDK wrote indistinguishable from one the web app wrote.

A workspace also fixes, at creation, an anonymization precision
(`month`/`day`/`hour`/`minute`/`second`): the web app truncates every date to
it *before* encrypting, so the discarded detail never exists anywhere. The
external API does not expose that setting, so the SDK cannot look it up.
Set `Settings.time_precision` (`DIAGNOS_TIME_PRECISION`) to the workspace's
value and the SDK applies the same truncation on every write.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Final, Literal, get_args

TimePrecision = Literal["month", "day", "hour", "minute", "second"]
"""A workspace's anonymization precision: every date is truncated to it before sealing (`Settings.time_precision`)."""
TIME_PRECISIONS: Final[tuple[str, ...]] = get_args(TimePrecision)

# `YYYY-MM-DD` is 10 characters; a longer string carries a time and needs an explicit offset.
_DATE_ONLY_LENGTH: Final[int] = 10


def _parse(value: date | datetime | str) -> datetime:
    """Convert a `date`, an aware `datetime` or an ISO 8601 string to an aware UTC `datetime`.

    A date alone (`date`, or `"YYYY-MM-DD"`) means midnight UTC, as
    `Date.parse` reads it. A time without a UTC offset is refused: it would
    mean a different instant on every machine, which is exactly the residual
    signal the web app's UTC-only rule exists to remove.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive datetime: pass an aware datetime (with tzinfo) or a date")
        return value.astimezone(UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f"{value!r} is not an ISO 8601 date") from None
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC)
        if len(value) == _DATE_ONLY_LENGTH:
            return parsed.replace(tzinfo=UTC)
        raise ValueError(f"{value!r} has a time but no UTC offset (add 'Z' or '+00:00')")
    raise ValueError(f"expected a date, datetime or ISO 8601 string, got {type(value).__name__}")


def _format(instant: datetime) -> str:
    """Format an aware UTC instant like `Date.toISOString()`: `YYYY-MM-DDTHH:MM:SS.sssZ`."""
    return (
        f"{instant.year:04d}-{instant.month:02d}-{instant.day:02d}T"
        f"{instant.hour:02d}:{instant.minute:02d}:{instant.second:02d}.{instant.microsecond // 1000:03d}Z"
    )


def to_iso_instant(value: date | datetime | str) -> str:
    """Return the web app's ISO 8601 string for `value`, with no truncation.

    >>> to_iso_instant(date(1984, 3, 2))
    '1984-03-02T00:00:00.000Z'

    Args:
        value: A `date`, an aware `datetime`, or an ISO 8601 string. A string with a time must carry a UTC offset;
            a date alone means midnight UTC.

    Returns:
        The instant in UTC as `YYYY-MM-DDTHH:MM:SS.sssZ`.

    Raises:
        ValueError: If `value` is a naive `datetime`, an unparseable string, a time without a UTC offset, or of
            another type.
    """
    return _format(_parse(value))


def truncate_timestamp(value: date | datetime | str, precision: TimePrecision) -> str:
    """Truncate `value` like the web app's `truncateTimestamp`: zero everything finer than `precision`, in UTC.

    `month` sets the day to 1; it keeps the month and does not zero it.

    >>> truncate_timestamp("1984-03-17T15:42:10Z", "month")
    '1984-03-01T00:00:00.000Z'

    Args:
        value: A `date`, an aware `datetime`, or an ISO 8601 string (see `to_iso_instant`).
        precision: The finest unit to keep: `month`, `day`, `hour`, `minute` or `second`.

    Returns:
        The truncated instant in UTC as `YYYY-MM-DDTHH:MM:SS.sssZ`.

    Raises:
        ValueError: If `value` is invalid (see `to_iso_instant`) or `precision` is not one of `TIME_PRECISIONS`.
    """
    instant = _parse(value)
    if precision not in TIME_PRECISIONS:
        raise ValueError(f"time precision must be one of {', '.join(TIME_PRECISIONS)}, got {precision!r}")
    instant = instant.replace(microsecond=0)
    if precision in ("minute", "hour", "day", "month"):
        instant = instant.replace(second=0)
    if precision in ("hour", "day", "month"):
        instant = instant.replace(minute=0)
    if precision in ("day", "month"):
        instant = instant.replace(hour=0)
    if precision == "month":
        instant = instant.replace(day=1)
    return _format(instant)
