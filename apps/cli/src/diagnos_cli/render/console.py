"""🇺🇸 The two `rich` consoles every command builds: results on `stdout`, progress/diagnostics on `stderr`.

Keeping them separate is what lets `--json` stay pipeable: a spinner or an
enrollment panel printed to `stdout` would land inside whatever a script
pipes into `jq`, so anything that is not the actual result always goes to
`stderr` instead.

🇧🇷 Os dois consoles `rich` que todo comando constrói: resultado na `stdout`, progresso/diagnóstico na `stderr`.

Mantê-los separados é o que permite `--json` continuar encadeável: um
spinner ou um painel de enrollment impresso na `stdout` cairia dentro do
que um script encadeia num `jq`, então tudo que não é o resultado de fato
vai para `stderr`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal

from rich.console import Console

if TYPE_CHECKING:
    from diagnos_cli.context import CliOptions


def get_console(opts: CliOptions) -> Console:
    """🇺🇸 The `stdout` console for results (tables, panels, JSON) — respects `--no-color`.

    🇧🇷 O console de `stdout` para resultados (tabelas, painéis, JSON) — respeita `--no-color`.
    """
    return Console(color_system=_color_system(opts), highlight=False)


def get_err_console(opts: CliOptions) -> Console:
    """🇺🇸 The `stderr` console for progress and diagnostics — never mixed into `--json` output.

    🇧🇷 O console de `stderr` para progresso e diagnóstico — nunca misturado à saída de `--json`.
    """
    return Console(color_system=_color_system(opts), stderr=True, highlight=False)


def _color_system(opts: CliOptions) -> Literal["auto"] | None:
    """🇺🇸 `None` — no ANSI escapes at all, bold included — for `--no-color` or `NO_COLOR`; else auto-detect.

    `rich`'s own `no_color` drops colors but keeps bold and dim, which still
    litters logs and `grep` output with escape codes.

    🇧🇷 `None` — nenhum escape ANSI, nem negrito — para `--no-color` ou `NO_COLOR`; senão detecção automática.

    O `no_color` do próprio `rich` tira as cores mas mantém negrito e
    esmaecido, o que ainda suja logs e saída de `grep` com códigos de escape.
    """
    return None if opts.no_color or os.environ.get("NO_COLOR") is not None else "auto"
