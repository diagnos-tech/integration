"""🇺🇸 The base command line: `diagnos docs | version | setup | help`, parsed with `argparse` alone.

This is what `diagnos` is until `diagnos[cli]` is installed, and the
contract every language wrapper copies (`wrappers/contract.json`). Any
other command — `diagnos login`, `diagnos patients …` — belongs to the full
command line: it answers with the one line that installs it and exit code
`EXIT_UNAVAILABLE`, instead of an "invalid choice" error. `--json` and
`--no-color` may come before or after the command, as in the full CLI.

🇧🇷 A linha de comando base: `diagnos docs | version | setup | help`, interpretada só com `argparse`.

É isto que o `diagnos` é até o `diagnos[cli]` ser instalado, e o contrato
que todo wrapper de linguagem copia (`wrappers/contract.json`). Qualquer
outro comando — `diagnos login`, `diagnos patients …` — pertence à linha de
comando completa: responde com a linha que a instala e o código de saída
`EXIT_UNAVAILABLE`, em vez de um erro de "escolha inválida". `--json` e
`--no-color` podem vir antes ou depois do comando, como na CLI completa.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Final

from .._extras import install_hint
from .._version import __version__
from .docs import TOPICS, docs
from .exit_codes import EXIT_OK, EXIT_UNAVAILABLE, EXIT_USAGE
from .output import Output, table
from .setup import TARGETS, setup
from .version import version

COMMANDS: Final = {
    "docs": "Help Center, Developer Central and Trust Center links · Links da Central de Ajuda, Developer Central "
    "e Trust Center",
    "version": "This installation: version, Python, extras · Esta instalação: versão, Python, extras",
    "setup": "Install the SDK, the CLI or the API, step by step · Instala o SDK, a CLI ou a API, passo a passo",
    "help": "This help, or a command's · Esta ajuda, ou a de um comando",
}
_GLOBAL_FLAGS: Final = ("--json", "--no-color")


def _parser(command: str) -> argparse.ArgumentParser:
    """🇺🇸 The `argparse` parser of one base command. 🇧🇷 O parser `argparse` de um comando da base."""
    parser = argparse.ArgumentParser(prog=f"diagnos {command}", description=COMMANDS[command])
    if command == "docs":
        parser.add_argument("topic", nargs="?", choices=TOPICS, help="Print only this URL · Imprime só esta URL")
        parser.add_argument("--open", action="store_true", help="Open it in the browser · Abre no navegador")
    elif command == "setup":
        parser.add_argument(
            "target", nargs="?", choices=[target.value for target in TARGETS], help="What to install · O que instalar"
        )
        parser.add_argument("--yes", "-y", action="store_true", help="Run without asking · Roda sem perguntar")
        parser.add_argument("--dry-run", action="store_true", help="Only print the plan · Só imprime o plano")
    elif command == "help":
        parser.add_argument("command", nargs="?", choices=tuple(COMMANDS), help="A command · Um comando")
    if command in ("docs", "version"):
        parser.add_argument("--json", action="store_true", help="Machine output · Saída para máquina")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors · Desliga cores ANSI")
    return parser


def _hoisted(argv: Sequence[str]) -> list[str]:
    """🇺🇸 `argv` with the global flags typed before the command moved after it, where its parser reads them.

    🇧🇷 `argv` com as flags globais digitadas antes do comando movidas para depois dele, onde o parser as lê.
    """
    first = next((index for index, arg in enumerate(argv) if arg not in _GLOBAL_FLAGS), len(argv))
    if first == len(argv):
        return list(argv)
    return [argv[first], *argv[:first], *argv[first + 1 :]]


def _help(out: Output) -> int:
    """🇺🇸 The overview: commands, then the extras `setup` installs.

    🇧🇷 A visão geral: comandos, e os extras que o `setup` instala.
    """
    tagline = "the diagnos vault from Python · o cofre diagnos no Python"
    out.line(f"{out.style(f'diagnos {__version__}', 'bold')} — {tagline}")
    out.line()
    out.line("Usage · Uso: diagnos <command> [options]")
    out.line()
    out.line(out.style("Commands · Comandos", "bold"))
    for row in table([(name, about) for name, about in COMMANDS.items()]):
        out.line(row)
    out.line()
    out.line(out.style("Install more · Instale mais", "bold"))
    for row in table([(f"diagnos setup {target}", about) for target, about in TARGETS.items()]):
        out.line(row)
    out.line()
    out.line("diagnos help <command> · the command's options · as opções do comando")
    return EXIT_OK


def _unknown(name: str, out: Output) -> int:
    """🇺🇸 A command this install does not have: an option typo, or the full CLI's.

    🇧🇷 Um comando que esta instalação não tem: um erro de digitação, ou um da CLI completa.
    """
    if name.startswith("-"):
        out.error(f"Unknown option · Opção desconhecida: {name}  (diagnos help)")
        return EXIT_USAGE
    out.error(f"`diagnos {name}` is part of the full command line · faz parte da linha de comando completa.")
    out.error(f"  {install_hint('cli')}")
    return EXIT_UNAVAILABLE


def main(argv: Sequence[str]) -> int:
    """🇺🇸 Runs one base command line and returns its exit code; never calls `sys.exit` itself.

    🇧🇷 Roda uma linha de comando da base e devolve o código de saída; nunca chama `sys.exit` ela mesma.
    """
    args = _hoisted(argv)
    if not args or args[0] in ("-h", "--help", *_GLOBAL_FLAGS):
        return _help(Output.terminal(no_color="--no-color" in args))
    if args[0] == "--version":
        Output.terminal().line(f"diagnos {__version__}")
        return EXIT_OK
    name, rest = args[0], args[1:]
    if name not in COMMANDS:
        return _unknown(name, Output.terminal())
    parser = _parser(name)
    try:
        options = parser.parse_args(rest)
    except SystemExit as exit_:
        return exit_.code if isinstance(exit_.code, int) else EXIT_USAGE
    out = Output.terminal(json_output=getattr(options, "json", False), no_color=options.no_color)
    if name == "docs":
        return docs(options.topic, open_browser=options.open, out=out)
    if name == "version":
        return version(out=out)
    if name == "setup":
        if options.target is None:
            parser.print_help(out.stdout)
            return EXIT_USAGE
        return setup(options.target, assume_yes=options.yes, dry_run=options.dry_run, out=out)
    if options.command in (None, "help"):
        return _help(out)
    _parser(options.command).print_help(out.stdout)
    return EXIT_OK
