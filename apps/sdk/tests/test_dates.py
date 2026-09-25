"""🇺🇸 `diagnos.dates`: the web app's date string and its anonymization truncation.

🇧🇷 `diagnos.dates`: a string de data do app web e o truncamento de anonimização dele.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from diagnos.dates import TIME_PRECISIONS, to_iso_instant, truncate_timestamp


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(1984, 3, 2), "1984-03-02T00:00:00.000Z"),
        ("1984-03-02", "1984-03-02T00:00:00.000Z"),
        ("1984-03-02T10:20:30Z", "1984-03-02T10:20:30.000Z"),
        ("1984-03-02T10:20:30.123456+00:00", "1984-03-02T10:20:30.123Z"),
        (datetime(1984, 3, 2, 23, 30, tzinfo=timezone(timedelta(hours=-3))), "1984-03-03T02:30:00.000Z"),
        (datetime(984, 1, 5, tzinfo=UTC), "0984-01-05T00:00:00.000Z"),
    ],
)
def test_to_iso_instant_matches_date_to_iso_string(value: object, expected: str) -> None:
    """🇺🇸 Same string `Date.toISOString()` produces, always UTC.

    🇧🇷 A mesma string do `Date.toISOString()`, sempre UTC.
    """
    assert to_iso_instant(value) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    ["not a date", "1984-03-02T10:20:30", datetime(1984, 3, 2, 10, 0), 19840302],
)
def test_to_iso_instant_refuses_ambiguous_or_invalid_input(value: object) -> None:
    """🇺🇸 Unparseable, naive or non-date input is a `ValueError`.

    🇧🇷 Entrada ilegível, sem fuso ou não-data é `ValueError`.
    """
    with pytest.raises(ValueError):
        to_iso_instant(value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("precision", "expected"),
    [
        ("second", "1984-03-17T15:42:10.000Z"),
        ("minute", "1984-03-17T15:42:00.000Z"),
        ("hour", "1984-03-17T15:00:00.000Z"),
        ("day", "1984-03-17T00:00:00.000Z"),
        ("month", "1984-03-01T00:00:00.000Z"),
    ],
)
def test_truncate_timestamp_matches_the_web_app(precision: str, expected: str) -> None:
    """🇺🇸 Each precision zeroes everything finer; `month` sets the day to 1.

    🇧🇷 Cada precisão zera o mais fino; `month` põe dia 1.
    """
    assert truncate_timestamp("1984-03-17T15:42:10.987Z", precision) == expected  # type: ignore[arg-type]


def test_truncate_timestamp_refuses_an_unknown_precision() -> None:
    """🇺🇸 Only the five workspace precisions exist. 🇧🇷 Só existem as cinco precisões de workspace."""
    assert TIME_PRECISIONS == ("month", "day", "hour", "minute", "second")
    with pytest.raises(ValueError, match="must be one of"):
        truncate_timestamp("1984-03-17", "year")  # type: ignore[arg-type]
