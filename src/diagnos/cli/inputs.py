"""🇺🇸 Turns `--file record.json` (`-` for stdin) or inline flags into the plain `dict` `create`/`update` accept.

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
import sys
from pathlib import Path
from typing import Any

import typer


def load_record(file: Path | None, inline: dict[str, Any]) -> dict[str, Any]:
    """🇺🇸 The record from `--file` (`-` reads stdin) or from the inline flags given — never a mix of both.

    Passing both used to keep the file and drop the flags without a word; a
    typo'd script then wrote the wrong record. Now it stops and names the
    flags to remove.

    🇧🇷 O registro vindo de `--file` (`-` lê o stdin) ou das flags inline dadas — nunca uma mistura dos dois.

    Passar os dois mantinha o arquivo e descartava as flags sem aviso; um
    script com erro de digitação gravava então o registro errado. Agora ele
    para e nomeia as flags a tirar.
    """
    fields = {key: value for key, value in inline.items() if value is not None}
    if file is not None:
        if fields:
            flags = ", ".join(f"--{key.replace('_', '-')}" for key in fields)
            raise typer.BadParameter(
                f"use --file or {flags}, not both · use --file ou {flags}, não os dois", param_hint="--file"
            )
        return _read_object(file)
    if not fields:
        raise typer.BadParameter(
            "pass --file, or at least one inline field · passe --file, ou ao menos um campo inline"
        )
    return fields


def _read_object(file: Path) -> dict[str, Any]:
    """🇺🇸 The JSON object in `file`, or on stdin for `-`. 🇧🇷 O objeto JSON em `file`, ou no stdin para `-`."""
    name = "stdin" if str(file) == "-" else str(file)
    try:
        text = sys.stdin.read() if str(file) == "-" else file.read_text(encoding="utf-8")
        data = json.loads(text)
    except OSError as exc:
        raise typer.BadParameter(f"cannot read {name} · não foi possível ler {name}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{name} is not valid JSON · {name} não é JSON válido: {exc}") from exc
    if not isinstance(data, dict):
        raise typer.BadParameter(f"{name} must contain a JSON object · {name} precisa conter um objeto JSON")
    return data
