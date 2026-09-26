"""🇺🇸 `make docs`: regenerate `docs/reference/*.json` from the code, at the paths `docs/site.json` declares.

`python -m scripts.docs.generate` writes the three files; `render_all` is
what `make docs-check` compares against the committed ones. The paths come
from the manifest's `reference` map, so the site and this script can never
disagree on where a file lives.

🇧🇷 `make docs`: regera `docs/reference/*.json` a partir do código, nos caminhos que `docs/site.json` declara.

`python -m scripts.docs.generate` grava os três arquivos; `render_all` é o
que o `make docs-check` compara com os commitados. Os caminhos vêm do mapa
`reference` do manifesto, então o site e este script nunca discordam de
onde um arquivo mora.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import cli, openapi, sdk, site
from .output import REPO_ROOT, head_commit, read_committed, render, stamp

# 🇺🇸 `(builder, sort_keys)` per reference kind — see `output.py` for why OpenAPI keeps FastAPI's order.
# 🇧🇷 `(construtor, sort_keys)` por tipo de referência — ver `output.py` para o porquê de o OpenAPI manter a ordem.
GENERATORS: dict[str, tuple[Callable[[], dict[str, Any]], bool]] = {
    "openapi": (openapi.build, False),
    "cli": (cli.build, True),
    "sdk": (sdk.build, True),
}


def render_all(root: Path = REPO_ROOT) -> dict[Path, str]:
    """🇺🇸 `{path: text}` of every reference file as the code produces it now.

    🇧🇷 `{caminho: texto}` de todo arquivo de referência como o código o produz agora.
    """
    references: dict[str, str] = site.load(root)["reference"]
    commit = head_commit(root)
    rendered: dict[Path, str] = {}
    for kind, (build, sort_keys) in GENERATORS.items():
        path = root / references[kind]
        rendered[path] = render(stamp(build(), read_committed(path), commit=commit), sort_keys=sort_keys)
    return rendered


def stale(root: Path = REPO_ROOT) -> list[str]:
    """🇺🇸 A problem line per reference file that differs from what `make docs` would write.

    🇧🇷 Uma linha de problema por arquivo de referência diferente do que o `make docs` gravaria.
    """
    problems = []
    for path, text in render_all(root).items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            where = path.relative_to(root)
            problems.append(f"{where}:1: stale, run `make docs` · desatualizado, rode `make docs`")
    return problems


def main() -> int:
    """🇺🇸 Writes every reference file that changed. 🇧🇷 Grava todo arquivo de referência que mudou."""
    for path, text in render_all().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote · gravado: {path.relative_to(REPO_ROOT)}")
        else:
            print(f"unchanged · sem mudança: {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
