"""🇺🇸 The "Examples" block at the bottom of every `--help`, written in the one shape the docs read back.

Each example is a real invocation on a `$ ` line with its description,
`English · Português`, on the line under it. `scripts/docs/cli.py` reads
exactly these lines into `cli.json`, so an example lives in one place —
here, next to the command — and shows up both in the terminal and on the
documentation site.

🇧🇷 O bloco "Exemplos" no fim de todo `--help`, escrito na única forma que a doc lê de volta.

Cada exemplo é uma invocação de verdade numa linha `$ ` com a descrição,
`English · Português`, na linha de baixo. O `scripts/docs/cli.py` lê
exatamente estas linhas para o `cli.json`, então um exemplo mora num lugar
só — aqui, ao lado do comando — e aparece tanto no terminal quanto no site de
documentação.
"""

from __future__ import annotations

HEADING = "Examples · Exemplos"


def examples(*items: tuple[str, str]) -> str:
    """🇺🇸 The epilog for `(command, "English · Português")` pairs; `command` starts with `diagnos`.

    🇧🇷 O epílogo para pares `(comando, "English · Português")`; `comando` começa com `diagnos`.
    """
    lines = [HEADING]
    for command, description in items:
        lines += ["", f"  $ {command}", f"    {description}"]
    return "\n".join(lines)
