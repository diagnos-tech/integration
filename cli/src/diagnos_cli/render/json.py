"""🇺🇸 `--json` output: plain `json.dumps` to `stdout`, deliberately never through `rich`.

A `rich.console.Console` wraps long lines to the terminal width, which
would silently corrupt a JSON document piped into `jq` the moment a field
made a line too long. Writing with the stdlib `json` module straight to
`stdout` instead means JSON mode is always byte-for-byte what `json.dumps`
produced, regardless of terminal width.

🇧🇷 Saída de `--json`: `json.dumps` puro na `stdout`, de propósito nunca por `rich`.

Um `rich.console.Console` quebra linha longa na largura do terminal, o que
corromperia em silêncio um documento JSON encadeado num `jq` assim que um
campo deixasse uma linha comprida demais. Escrever com o módulo `json` da
stdlib direto na `stdout` faz o modo JSON ser sempre, byte a byte, o que
`json.dumps` produziu, independente da largura do terminal.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from pydantic import BaseModel


def _to_jsonable(value: Any) -> Any:
    """🇺🇸 Recursively turns pydantic models (and containers of them) into plain JSON-safe data.

    🇧🇷 Transforma modelos pydantic (e contêineres deles), de forma recursiva, em dado seguro para JSON.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


def print_json(data: Any) -> None:
    """🇺🇸 Writes `data` as pretty-printed JSON straight to `stdout`, bypassing `rich` entirely.

    🇧🇷 Escreve `data` como JSON formatado direto na `stdout`, sem passar por `rich`.
    """
    sys.stdout.write(json.dumps(_to_jsonable(data), indent=2, ensure_ascii=False, sort_keys=True))
    sys.stdout.write("\n")
