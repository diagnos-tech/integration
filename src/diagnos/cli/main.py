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
from rich.console import Console
from rich.markup import escape

from diagnos import DiagnosError
from diagnos._version import __version__
from diagnos._wrapper.app import COMMANDS as BASE_COMMANDS
from diagnos.cli.agent.dispatch import dispatch
from diagnos.cli.argv import hoist_global_options
from diagnos.cli.commands import base, exams, files, groups, login, logout, patients, session, status, whoami
from diagnos.cli.context import CliOptions
from diagnos.cli.examples import examples
from diagnos.cli.exit_codes import EXIT_GENERAL, classify

typer_app = typer.Typer(
    name="diagnos",
    help="The diagnos vault, from your terminal · O cofre diagnos, do seu terminal",
    add_completion=False,
    epilog=examples(
        (
            "diagnos login",
            "Paste the service account token once; it goes to the system keyring · Cole o token uma vez; ele vai "
            "para o chaveiro do sistema",
        ),
        (
            "diagnos --json patients list --all",
            "Every patient, as JSON for scripts · Todos os pacientes, em JSON para scripts",
        ),
        ("diagnos --quiet files download NODE_ID", "No spinner, for cron jobs · Sem spinner, para cron"),
    ),
)
typer_app.add_typer(patients.app, name="patients")
typer_app.add_typer(exams.app, name="exams")
typer_app.add_typer(files.app, name="files")
typer_app.add_typer(session.app, name="session")
typer_app.command(
    "login",
    help="Store the service account token safely · Guarda o token da conta de serviço com segurança",
    epilog=examples(
        (
            "diagnos login",
            "Hidden input, CRC check, whoami, then the system keyring (else OpenBao) · Entrada oculta, CRC, whoami, "
            "depois o chaveiro do sistema (senão o OpenBao)",
        ),
        ("diagnos login --store openbao", "Keep it in OpenBao (OPENBAO_ADDR) · Guarda no OpenBao (OPENBAO_ADDR)"),
        ("diagnos --json login", "Identity, groups and where it was stored · Identidade, grupos e onde foi guardado"),
    ),
)(login.login)
typer_app.command(
    "whoami",
    help="Which token this is, proven against the vault · Qual token é este, provado contra o cofre",
    epilog=examples(
        ("diagnos whoami", "Identity, token source, groups · Identidade, origem do token, grupos"),
        ("diagnos --json whoami", "The same, as JSON · O mesmo, em JSON"),
    ),
)(whoami.whoami)
typer_app.command(
    "status",
    help="Token, OpenBao and SDK version · Token, OpenBao e versão do SDK",
    epilog=examples(
        ("diagnos status", "Parses the token locally; no network · Lê o token localmente; sem rede"),
        ("diagnos status --check", "Also unlock and list the granted groups · Também desbloqueia e lista os grupos"),
    ),
)(status.status)
typer_app.command(
    "logout",
    help="Forget the stored token · Esquece o token guardado",
    epilog=examples(
        ("diagnos logout", "Delete it from the keyring and OpenBao · Apaga do chaveiro e do OpenBao"),
        ("diagnos --json logout", "Where it was removed from, as JSON · De onde foi removido, em JSON"),
    ),
)(logout.logout)
typer_app.command(
    "groups",
    help="Granted security groups · Security groups concedidos",
    epilog=examples(
        ("diagnos groups", "One security group id per line · Um id de security group por linha"),
        ("diagnos --json groups", "The same list, as JSON · A mesma lista, em JSON"),
    ),
)(groups.groups)

# 🇺🇸 The base's four commands, last: the same help text and behavior as `pip install diagnos` alone.
# 🇧🇷 Os quatro comandos da base, por último: o mesmo texto de ajuda e comportamento do `pip install diagnos` sozinho.
typer_app.command(
    "docs",
    help=BASE_COMMANDS["docs"],
    epilog=examples(
        ("diagnos docs", "The three sites, one per line · Os três sites, um por linha"),
        ("diagnos docs dev --open", "Open Developer Central in the browser · Abre a Developer Central no navegador"),
    ),
)(base.docs)
typer_app.command(
    "version",
    help=BASE_COMMANDS["version"],
    epilog=examples(
        ("diagnos version", "Version, interpreter, platform, extras · Versão, interpretador, plataforma, extras"),
        ("diagnos --json version", "The same, as JSON for bug reports · O mesmo, em JSON para relatos de bug"),
    ),
)(base.version)
typer_app.command(
    "setup",
    help=BASE_COMMANDS["setup"],
    epilog=examples(
        ("diagnos setup api", "Pull and verify the API image · Baixa e verifica a imagem da API"),
        ("diagnos setup sdk --dry-run", "Only show what would run · Só mostra o que rodaria"),
    ),
)(base.setup)
typer_app.command(
    "help",
    help=BASE_COMMANDS["help"],
    epilog=examples(
        ("diagnos help patients list", "The same as `diagnos patients list --help` · O mesmo que `--help`")
    ),
)(base.help_)


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
    vault_url: str | None = typer.Option(
        None, "--vault-url", help="Overrides DIAGNOS_VAULT_URL · Sobrescreve DIAGNOS_VAULT_URL"
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        help=(
            "Service account token for this run (or a legacy apikey- one); prefer `diagnos login` · Token da conta "
            "de serviço nesta execução (ou um apikey- legado); prefira `diagnos login`"
        ),
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
