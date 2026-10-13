"""🇺🇸 `diagnos docs | version | setup | help` in the full CLI — the base's four commands, through typer.

The work is the base's own (`diagnos._wrapper`); these adapters only map
typer's parameters and the global `--json`/`--no-color` onto it, so a
command behaves the same whether `diagnos[cli]` is installed or not.
`apps/cli/tests/test_base_commands.py` holds every option here equal to the
base's `argparse` parser, so the two front-ends cannot drift apart.

🇧🇷 `diagnos docs | version | setup | help` na CLI completa — os quatro comandos da base, pelo typer.

O trabalho é da própria base (`diagnos._wrapper`); estes adaptadores só
mapeiam os parâmetros do typer e o `--json`/`--no-color` globais para ela,
então um comando se comporta igual com ou sem o `diagnos[cli]` instalado. O
`apps/cli/tests/test_base_commands.py` mantém toda opção daqui igual à do
parser `argparse` da base, para os dois front-ends não se afastarem.
"""

from __future__ import annotations

import typer

from diagnos._wrapper.docs import Topic
from diagnos._wrapper.docs import docs as base_docs
from diagnos._wrapper.output import Output
from diagnos._wrapper.setup import Target
from diagnos._wrapper.setup import setup as base_setup
from diagnos._wrapper.version import version as base_version
from diagnos.cli.context import CliOptions


def _out(ctx: typer.Context) -> Output:
    """🇺🇸 The base's output, honoring the global `--json`/`--no-color`.

    🇧🇷 A saída da base, respeitando o `--json`/`--no-color` globais.
    """
    opts: CliOptions = ctx.obj
    return Output.terminal(json_output=opts.json_output, no_color=opts.no_color)


def docs(
    ctx: typer.Context,
    topic: Topic | None = typer.Argument(None, show_default=False, help="Print only this URL · Imprime só esta URL"),
    open_browser: bool = typer.Option(False, "--open", help="Open it in the browser · Abre no navegador"),
) -> None:
    """🇺🇸 `diagnos docs`. 🇧🇷 `diagnos docs`."""
    raise typer.Exit(base_docs(topic, open_browser=open_browser, out=_out(ctx)))


def version(ctx: typer.Context) -> None:
    """🇺🇸 `diagnos version`. 🇧🇷 `diagnos version`."""
    raise typer.Exit(base_version(out=_out(ctx)))


def setup(
    ctx: typer.Context,
    target: Target = typer.Argument(..., help="What to install · O que instalar"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Run without asking · Roda sem perguntar"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Only print the plan · Só imprime o plano"),
) -> None:
    """🇺🇸 `diagnos setup`. 🇧🇷 `diagnos setup`."""
    raise typer.Exit(base_setup(target, assume_yes=yes, dry_run=dry_run, out=_out(ctx)))


def help_(
    command: list[str] | None = typer.Argument(None, show_default=False, help="A command · Um comando"),
) -> None:
    """🇺🇸 `diagnos help [COMMAND…]`: the same as `diagnos [COMMAND…] --help`.

    🇧🇷 `diagnos help [COMANDO…]`: o mesmo que `diagnos [COMANDO…] --help`.
    """
    from diagnos.cli.main import run  # 🇺🇸 `main` registers this module 🇧🇷 o `main` registra este módulo

    raise typer.Exit(run([*(command or []), "--help"]))
