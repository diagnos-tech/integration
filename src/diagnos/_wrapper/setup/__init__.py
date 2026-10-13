"""🇺🇸 `diagnos setup sdk | cli | api` — one layer installed for you, step by step, or exactly told how.

Each target checks what it needs (`uv` for the Python layers, Docker for
the API), builds a plan, shows every command, asks once and runs it. A
missing tool ends with its official install page and exit code
`EXIT_UNAVAILABLE`, never with an attempt to install it. `--dry-run` only
prints the plan; `--yes` runs it without asking (for scripts and CI).

🇧🇷 `diagnos setup sdk | cli | api` — uma camada instalada para você, passo a passo, ou dito exatamente como.

Cada alvo confere o que precisa (`uv` para as camadas Python, Docker para a
API), monta um plano, mostra todo comando, pergunta uma vez e roda. Uma
ferramenta ausente termina com a página oficial de instalação dela e o
código de saída `EXIT_UNAVAILABLE`, nunca com uma tentativa de instalá-la.
`--dry-run` só imprime o plano; `--yes` roda sem perguntar (para scripts e CI).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Final, TextIO

from ..output import Output
from . import api, python
from .run import Plan, carry_out


class Target(StrEnum):
    """🇺🇸 What `diagnos setup` installs: one layer each. 🇧🇷 O que o `diagnos setup` instala: uma camada cada."""

    SDK = "sdk"
    CLI = "cli"
    API = "api"


TARGETS: Final[dict[Target, str]] = {
    Target.SDK: "The Python SDK, in your project (uv) · O SDK Python, no seu projeto (uv)",
    Target.CLI: "The full command line (uv) · A linha de comando completa (uv)",
    Target.API: "The REST API's signed container image (Docker) · A imagem assinada da API REST (Docker)",
}


def setup(
    target: str,
    *,
    assume_yes: bool,
    dry_run: bool,
    out: Output,
    stdin: TextIO | None = None,
    cwd: Path | None = None,
) -> int:
    """🇺🇸 Plans `target` and carries it out; returns the exit code (`exit_codes`).

    🇧🇷 Planeja o `target` e o executa; devolve o código de saída (`exit_codes`).
    """
    planners: dict[Target, Callable[[Output], Plan | int]] = {
        Target.SDK: lambda out: python.sdk(out, cwd=cwd or Path.cwd()),
        Target.CLI: python.cli,
        Target.API: api.api,
    }
    plan = planners[Target(target)](out)
    if isinstance(plan, int):
        return plan
    return carry_out(plan, out, assume_yes=assume_yes, dry_run=dry_run, stdin=stdin or sys.stdin)
