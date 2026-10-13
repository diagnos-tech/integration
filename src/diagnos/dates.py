"""🇺🇸 Dates the way the web app writes them: UTC ISO 8601 instants, optionally truncated to a precision.

Every date inside a sealed record (`birth_date`, `exam_date`) is stored as
the string JavaScript's `Date.toISOString()` produces —
`YYYY-MM-DDTHH:MM:SS.sssZ`, always UTC. Writing the same shape keeps a
record the SDK wrote indistinguishable from one the web app wrote.

A workspace also fixes, at creation, an anonymization precision
(`month`/`day`/`hour`/`minute`/`second`): the web app truncates every date to
it *before* encrypting, so the discarded detail never exists anywhere. The
external API does not expose that setting, so the SDK cannot look it up —
set `Settings.time_precision` (`DIAGNOS_TIME_PRECISION`) to the workspace's
value and the SDK applies the same truncation on every write.

🇧🇷 Datas do jeito que o app web as grava: instantes ISO 8601 em UTC, opcionalmente truncados a uma precisão.

Toda data dentro de um registro selado (`birth_date`, `exam_date`) é
gravada como a string que o `Date.toISOString()` do JavaScript produz —
`YYYY-MM-DDTHH:MM:SS.sssZ`, sempre UTC. Gravar a mesma forma deixa um
registro que o SDK gravou indistinguível de um que o app web gravou.

Um workspace também fixa, na criação, uma precisão de anonimização
(`month`/`day`/`hour`/`minute`/`second`): o app web trunca toda data nela
*antes* de cifrar, então o detalhe descartado nunca existe em lugar nenhum.
A API externa não expõe essa configuração, então o SDK não consegue
consultá-la — defina `Settings.time_precision` (`DIAGNOS_TIME_PRECISION`)
com o valor do workspace e o SDK aplica o mesmo truncamento em toda gravação.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Final, Literal, get_args

TimePrecision = Literal["month", "day", "hour", "minute", "second"]
"""🇺🇸 A workspace's anonymization precision: every date is truncated to it before sealing (`Settings.time_precision`).

🇧🇷 A precisão de anonimização de um workspace: toda data é truncada nela antes de selar (`Settings.time_precision`).
"""
TIME_PRECISIONS: Final[tuple[str, ...]] = get_args(TimePrecision)

# 🇺🇸 `YYYY-MM-DD` is 10 characters; a longer string carries a time and needs an explicit offset.
# 🇧🇷 `YYYY-MM-DD` tem 10 caracteres; uma string mais longa traz hora e precisa de fuso explícito.
_DATE_ONLY_LENGTH: Final[int] = 10


def _parse(value: date | datetime | str) -> datetime:
    """🇺🇸 An aware UTC `datetime` from a `date`, an aware `datetime` or an ISO 8601 string.

    A date alone (`date`, or `"YYYY-MM-DD"`) means midnight UTC, as
    `Date.parse` reads it. A time without a UTC offset is refused: it would
    mean a different instant on every machine, which is exactly the residual
    signal the web app's UTC-only rule exists to remove.

    🇧🇷 Um `datetime` UTC com fuso a partir de `date`, `datetime` com fuso ou string ISO 8601.

    Só a data (`date`, ou `"YYYY-MM-DD"`) significa meia-noite UTC, como o
    `Date.parse` a lê. Hora sem deslocamento de UTC é recusada: ela
    significaria um instante diferente em cada máquina, que é exatamente o
    sinal residual que a regra só-UTC do app web existe para apagar.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError(
                "naive datetime: pass an aware datetime (with tzinfo) or a date · datetime sem fuso: passe um "
                "datetime com tzinfo ou uma date"
            )
        return value.astimezone(UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f"{value!r} is not an ISO 8601 date · {value!r} não é uma data ISO 8601") from None
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC)
        if len(value) == _DATE_ONLY_LENGTH:
            return parsed.replace(tzinfo=UTC)
        raise ValueError(
            f"{value!r} has a time but no UTC offset (add 'Z' or '+00:00') · {value!r} tem hora mas não tem "
            "deslocamento de UTC (acrescente 'Z' ou '+00:00')"
        )
    raise ValueError(
        f"expected a date, datetime or ISO 8601 string, got {type(value).__name__} · esperava date, datetime ou "
        f"string ISO 8601, veio {type(value).__name__}"
    )


def _format(instant: datetime) -> str:
    """🇺🇸 `Date.toISOString()`: `YYYY-MM-DDTHH:MM:SS.sssZ`. 🇧🇷 `Date.toISOString()`: `YYYY-MM-DDTHH:MM:SS.sssZ`."""
    return (
        f"{instant.year:04d}-{instant.month:02d}-{instant.day:02d}T"
        f"{instant.hour:02d}:{instant.minute:02d}:{instant.second:02d}.{instant.microsecond // 1000:03d}Z"
    )


def to_iso_instant(value: date | datetime | str) -> str:
    """🇺🇸 The web app's string for `value`, with no truncation.

    >>> to_iso_instant(date(1984, 3, 2))
    '1984-03-02T00:00:00.000Z'

    🇧🇷 A string do app web para `value`, sem truncamento.
    """
    return _format(_parse(value))


def truncate_timestamp(value: date | datetime | str, precision: TimePrecision) -> str:
    """🇺🇸 `truncateTimestamp` from the web app: zero everything finer than `precision`, in UTC.

    `month` sets the day to 1 (it keeps the month, it does not zero it).

    >>> truncate_timestamp("1984-03-17T15:42:10Z", "month")
    '1984-03-01T00:00:00.000Z'

    🇧🇷 O `truncateTimestamp` do app web: zera tudo que é mais fino que `precision`, em UTC.

    `month` põe o dia em 1 (mantém o mês, não o zera).
    """
    instant = _parse(value)
    if precision not in TIME_PRECISIONS:
        raise ValueError(
            f"time precision must be one of {', '.join(TIME_PRECISIONS)}, got {precision!r} · a precisão precisa "
            f"ser uma de {', '.join(TIME_PRECISIONS)}, veio {precision!r}"
        )
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
