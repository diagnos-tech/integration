"""🇺🇸 Turns `--file record.json` or a handful of inline flags into the plain `dict` the SDK's `create`/`update` accept.

`Patients.create`/`Exams.create` validate a `Mapping[str, Any]` through
their pydantic record model themselves (`resources/_documents.py`'s
`coerce_record`) — this module never constructs a `PatientRecord`/
`ExamRecord` itself, it only assembles the dict and lets the SDK be the one
place that validates it.

🇧🇷 Transforma `--file record.json` ou algumas flags inline no `dict` puro
que `create`/`update` do SDK aceitam.

`Patients.create`/`Exams.create` validam um `Mapping[str, Any]` pelo próprio
modelo pydantic do registro (`coerce_record` de `resources/_documents.py`)
— este módulo nunca constrói um `PatientRecord`/`ExamRecord` ele mesmo, só
monta o dict e deixa o SDK ser o único lugar que o valida.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer


def load_record(file: Path | None, inline: dict[str, Any]) -> dict[str, Any]:
    """🇺🇸 `--file` wins outright; otherwise the non-`None` inline flags become the record fields.

    🇧🇷 `--file` vence direto; senão, as flags inline não-`None` viram os campos do registro.
    """
    if file is not None:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except OSError as exc:
            raise typer.BadParameter(f"cannot read {file} · não foi possível ler {file}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"{file} is not valid JSON · {file} não é JSON válido: {exc}") from exc
        if not isinstance(data, dict):
            raise typer.BadParameter(f"{file} must contain a JSON object · {file} precisa conter um objeto JSON")
        return data
    fields = {key: value for key, value in inline.items() if value is not None}
    if not fields:
        raise typer.BadParameter(
            "pass --file, or at least one inline field · passe --file, ou ao menos um campo inline"
        )
    return fields
