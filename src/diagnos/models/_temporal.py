"""Date/time handling shared by document streams and clinical records: parsing and the caller-vs-vault write rule.

`_instant` backs the draft-vs-version precedence rule (`_index.py`);
`IsoInstant`/`_iso_instant` back every date-shaped record field
(`PatientRecord.birth_date`, `ExamRecord.exam_date`): a caller's `date`,
aware `datetime` or ISO string is normalized the way the web app writes it,
while plaintext already decrypted from the vault is trusted as-is.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BeforeValidator, ValidationInfo

from diagnos.dates import to_iso_instant

from ._shared import _from_vault


def _instant(value: str) -> datetime | None:
    """Parse like `Date.parse` for the precedence rule: an aware `datetime`, or `None` when unparseable."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _iso_instant(value: Any, info: ValidationInfo) -> Any:
    """Accept a `date` or aware `datetime` and write it the way the web app does (`YYYY-MM-DDTHH:MM:SS.sssZ`).

    A string from the caller must parse as ISO 8601; a string from the
    vault is kept exactly as stored.
    """
    if value is None or _from_vault(info):
        return value
    return to_iso_instant(value)


# A date field: `date`/aware `datetime`/ISO string in, the web app's UTC instant string out.
IsoInstant = Annotated[str | None, BeforeValidator(_iso_instant)]
