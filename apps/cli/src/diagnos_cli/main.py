"""🇺🇸 The `diagnos` entry point: wires every command group and translates SDK exceptions into exit codes.

`app` (the name `apps/cli/pyproject.toml`'s `[project.scripts]` points at) is a
plain function, not the `typer.Typer()` instance — `click`'s `standalone_mode`
only catches its own `ClickException`/`Abort`, so any `DiagnosError` a
command raises would otherwise print a raw Python traceback and exit `1`.
Wrapping the one call to the Typer app here, instead of duplicating a
try/except in every command, is what makes `exit_codes.classify` apply
uniformly and keeps every command function itself free of error-handling
noise.

🇧🇷 O ponto de entrada `diagnos`: conecta todo grupo de comando e traduz
exceções do SDK em códigos de saída.

`app` (o nome que `[project.scripts]` de `apps/cli/pyproject.toml` aponta) é uma
função simples, não a instância de `typer.Typer()` — o `standalone_mode` do
`click` só pega a própria `ClickException`/`Abort`, então qualquer
`DiagnosError` que um comando lance, do contrário, imprimiria um traceback
Python cru e sairia com `1`. Envolver a única chamada à app Typer aqui, em
vez de duplicar um try/except em cada comando, é o que faz
`exit_codes.classify` valer de forma uniforme e mantém toda função de
comando livre de ruído de tratamento de erro.
"""

from __future__ import annotations

import os
import sys

import typer
from diagnos import DiagnosError
from rich.console import Console
from rich.markup import escape

from diagnos_cli import __version__
from diagnos_cli.agent.dispatch import dispatch
from diagnos_cli.argv import hoist_global_options
from diagnos_cli.commands import exams, files, groups, login, logout, patients, session, status
from diagnos_cli.context import CliOptions
from diagnos_cli.exit_codes import EXIT_GENERAL, classify

typer_app = typer.Typer(
    name="diagnos",
    help="The diagnos vault, from your terminal · O cofre diagnos, do seu terminal.",
    epilog="Start here · Comece aqui:  diagnos login  →  diagnos patients list  →  diagnos logout",
    add_completion=False,
)
typer_app.add_typer(patients.app, name="patients")
typer_app.add_typer(exams.app, name="exams")
typer_app.add_typer(files.app, name="files")
typer_app.add_typer(session.app, name="session")
typer_app.command("login", help="Enroll and show what was granted · Faz enrollment e mostra o que foi concedido")(
    login.login
)
typer_app.command("status", help="Token, OpenBao and SDK version · Token, OpenBao e versão do SDK")(status.status)
typer_app.command("logout", help="Lock the session and stop the agent · Trava a sessão e para o agente")(logout.logout)
typer_app.command("groups", help="Granted security groups · Security groups concedidos")(groups.groups)


def _version_callback(value: bool) -> None:
    """🇺🇸 `--version`: prints and exits before any other option is validated (`is_eager=True` below).

    🇧🇷 `--version`: imprime e sai antes de qualquer outra opção ser validada (`is_eager=True` abaixo).
    """
    if value:
        typer.echo(f"diagnos {__version__}")
        raise typer.Exit()


@typer_app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Machine output · Saída para máquina"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="No spinners/progress · Sem spinners/progresso"),
    vault_url: str | None = typer.Option(None, "--vault-url", help="Overrides DIAGNOS_VAULT_URL"),
    token: str | None = typer.Option(
        None,
        "--token",
        help="Overrides DIAGNOS_API_TOKEN · Sobrescreve DIAGNOS_API_TOKEN",
        show_default=False,
    ),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI colors · Desliga cores ANSI"),
    version: bool | None = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True, help="Show the version · Mostra a versão"
    ),
) -> None:
    """🇺🇸 Root command: stores the global options on `ctx.obj` for every subcommand to read.

    🇧🇷 Comando raiz: guarda as opções globais em `ctx.obj` para todo subcomando ler.
    """
    ctx.obj = CliOptions(json_output=json_output, quiet=quiet, vault_url=vault_url, token=token, no_color=no_color)
    if ctx.invoked_subcommand is None:
        # 🇺🇸 A bare `diagnos` is someone finding their way, not a mistake: the help, and success.
        # 🇧🇷 Um `diagnos` sozinho é alguém se orientando, não um erro: a ajuda, e sucesso.
        help_text = ctx.get_help()  # 🇺🇸 rich prints it already and returns "" 🇧🇷 o rich já imprime e devolve ""
        if help_text:
            typer.echo(help_text)
        raise typer.Exit()


def run(argv: list[str]) -> int:
    """🇺🇸 Runs one `diagnos` command line and returns its exit code — here, or inside the session agent.

    A `--no-color`/`NO_COLOR` check on the raw argv, instead of reading
    `ctx.obj`, is deliberate: an error can originate before `main()` even
    finishes parsing (e.g. a malformed `--vault-url`), so this has to work
    without assuming the callback ever ran.

    🇧🇷 Roda uma linha de comando `diagnos` e devolve o código de saída — aqui, ou dentro do agente de sessão.

    Conferir `--no-color`/`NO_COLOR` no argv cru, em vez de ler `ctx.obj`, é
    de propósito: um erro pode se originar antes até do `main()` terminar de
    interpretar (ex.: um `--vault-url` malformado), então isto precisa
    funcionar sem supor que o callback já rodou.
    """
    no_color = "--no-color" in argv or os.environ.get("NO_COLOR") is not None
    err_console = Console(stderr=True, color_system=None if no_color else "auto", highlight=False)
    try:
        typer_app(args=argv, prog_name="diagnos")
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except DiagnosError as exc:
        code, label = classify(exc)
        err_console.print(f"[bold red]{label}[/bold red] — {exc}")
        return code
    except OSError as exc:
        # 🇺🇸 A local file problem (a missing `-o` directory, an unreadable upload) is the user's to fix, not a crash.
        # 🇧🇷 Um problema de arquivo local (diretório de `-o` ausente, upload ilegível) é para o usuário corrigir, não
        #    uma quebra.
        err_console.print(f"[bold red]I/O error · Erro de E/S[/bold red] — {escape(str(exc))}")
        return EXIT_GENERAL
    return 0


def app() -> None:
    """🇺🇸 The console-script entry point: global options anywhere, the session agent when running, else in-process.

    🇧🇷 O ponto de entrada do console-script: opções globais em qualquer lugar, o agente de sessão quando rodando,
    senão no próprio processo.
    """
    argv = hoist_global_options(sys.argv[1:])
    code = dispatch(argv)
    raise SystemExit(run(argv) if code is None else code)
