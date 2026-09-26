"""🇺🇸 Date/time handling shared by document streams and clinical records: parsing and the caller-vs-vault write rule.

`_instant` backs the draft-vs-version precedence rule (`_index.py`);
`IsoInstant`/`_iso_instant` back every date-shaped record field
(`PatientRecord.birth_date`, `ExamRecord.exam_date`): a caller's `date`,
aware `datetime` or ISO string is normalized the way the web app writes it,
while plaintext already decrypted from the vault is trusted as-is.

🇧🇷 Data/hora compartilhada por fluxos de documento e registros clínicos: parsing e a regra de
gravação quem-chama-vs-cofre.

`_instant` sustenta a regra de precedência rascunho-vs-versão
(`_index.py`); `IsoInstant`/`_iso_instant` sustentam todo campo de data de
registro (`PatientRecord.birth_date`, `ExamRecord.exam_date`): um `date`,
`datetime` com fuso ou string ISO de quem chama é normalizado do jeito que o
app web grava, enquanto texto claro já decifrado do cofre é confiado como
está.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BeforeValidator, ValidationInfo

from diagnos.dates import to_iso_instant

from ._shared import _from_vault


def _instant(value: str) -> datetime | None:
    """🇺🇸 `Date.parse` for the precedence rule: an aware `datetime`, or `None` when unparseable.

    🇧🇷 O `Date.parse` da regra de precedência: um `datetime` com fuso, ou `None` quando não dá para ler.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _iso_instant(value: Any, info: ValidationInfo) -> Any:
    """🇺🇸 Accepts a `date`/aware `datetime` and writes it the way the web app does (`YYYY-MM-DDTHH:MM:SS.sssZ`).

    A string from the caller must parse as ISO 8601; a string from the
    vault is kept exactly as stored.

    🇧🇷 Aceita `date`/`datetime` com fuso e grava do jeito que o app web grava (`YYYY-MM-DDTHH:MM:SS.sssZ`).

    Uma string de quem chama precisa ser ISO 8601 válida; uma string vinda
    do cofre fica exatamente como foi gravada.
    """
    if value is None or _from_vault(info):
        return value
    return to_iso_instant(value)


# 🇺🇸 A date field: `date`/aware `datetime`/ISO string in, the web app's UTC instant string out.
# 🇧🇷 Um campo de data: `date`/`datetime` com fuso/string ISO na entrada, o instante UTC do app web na saída.
IsoInstant = Annotated[str | None, BeforeValidator(_iso_instant)]
