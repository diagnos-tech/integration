"""🇺🇸 How a generated JSON is written: deterministic text, and a `generatedFrom` that never churns on its own.

Determinism is what makes `make docs-check` possible at all: regenerating
must produce byte-identical files when the code did not change, so the
freshness check can be a plain text comparison. Two rules get there:

- the text is always `json.dumps(indent=2, ensure_ascii=False)` plus one
  trailing newline; `sort_keys` for the documents this repo shapes
  (`cli.json`, `sdk.json`), declaration order for `openapi.json` — sorting
  would scramble the field order of every schema the site shows;
- `generatedFrom.commit` is the commit the reference was *last regenerated
  on top of*: it is carried over from the committed file while nothing else
  changed, and only restamped with `HEAD` when the content really moved.
  Stamping `HEAD` blindly would make every commit stale the next one.

🇧🇷 Como um JSON gerado é gravado: texto determinístico, e um `generatedFrom` que nunca muda sozinho.

Determinismo é o que torna o `make docs-check` possível: regerar precisa
produzir arquivos idênticos byte a byte quando o código não mudou, para a
checagem de atualidade ser uma comparação simples de texto. Duas regras
chegam lá:

- o texto é sempre `json.dumps(indent=2, ensure_ascii=False)` mais uma quebra
  de linha final; `sort_keys` nos documentos que este repo molda (`cli.json`,
  `sdk.json`), ordem de declaração no `openapi.json` — ordenar embaralharia a
  ordem dos campos de todo schema que o site mostra;
- `generatedFrom.commit` é o commit sobre o qual a referência foi *regerada
  pela última vez*: é mantido do arquivo commitado enquanto nada mais mudou,
  e só recebe o `HEAD` quando o conteúdo mudou de verdade. Carimbar o `HEAD`
  às cegas deixaria todo commit velho já no seguinte.
"""

from __future__ import annotations

import json
import subprocess
from importlib.metadata import version
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1


def render(document: object, *, sort_keys: bool) -> str:
    """🇺🇸 The exact text a generated file holds. 🇧🇷 O texto exato que um arquivo gerado guarda."""
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=sort_keys) + "\n"


def head_commit(root: Path = REPO_ROOT) -> str:
    """🇺🇸 Short SHA of `HEAD`, or `unknown` outside a git checkout (a source tarball).

    🇧🇷 SHA curto do `HEAD`, ou `unknown` fora de um checkout git (um tarball de fonte).
    """
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def generated_from(package: str) -> dict[str, str]:
    """🇺🇸 The contract's `GeneratedFrom`, with the commit left for `stamp` to decide.

    🇧🇷 O `GeneratedFrom` do contrato, com o commit deixado para `stamp` decidir.
    """
    return {"package": package, "version": version(package), "commit": ""}


def stamp(fresh: dict[str, Any], committed: dict[str, Any] | None, *, commit: str) -> dict[str, Any]:
    """🇺🇸 `fresh` with `generatedFrom.commit` set: the committed one if nothing else changed, else `commit`.

    🇧🇷 `fresh` com `generatedFrom.commit` definido: o commitado se nada mais mudou, senão `commit`.
    """
    if "generatedFrom" not in fresh:
        return fresh
    previous = committed.get("generatedFrom", {}).get("commit") if committed else None
    carried = {**fresh, "generatedFrom": {**fresh["generatedFrom"], "commit": previous}}
    if previous and committed is not None and carried == committed:
        return carried
    return {**fresh, "generatedFrom": {**fresh["generatedFrom"], "commit": commit}}


def read_committed(path: Path) -> dict[str, Any] | None:
    """🇺🇸 The JSON currently on disk, or `None` when it does not exist or does not parse.

    🇧🇷 O JSON que está no disco agora, ou `None` quando não existe ou não é lido.
    """
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None
