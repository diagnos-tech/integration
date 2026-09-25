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

from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from diagnos_cli.context import CliOptions


def get_console(opts: CliOptions) -> Console:
    """🇺🇸 The `stdout` console for results (tables, panels, JSON) — respects `--no-color`.

    🇧🇷 O console de `stdout` para resultados (tabelas, painéis, JSON) — respeita `--no-color`.
    """
    return Console(no_color=opts.no_color, highlight=False)


def get_err_console(opts: CliOptions) -> Console:
    """🇺🇸 The `stderr` console for progress and diagnostics — never mixed into `--json` output.

    🇧🇷 O console de `stderr` para progresso e diagnóstico — nunca misturado à saída de `--json`.
    """
    return Console(no_color=opts.no_color, stderr=True, highlight=False)
