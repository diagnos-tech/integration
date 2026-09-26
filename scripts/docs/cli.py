"""🇺🇸 `cli.json`: every `diagnos` command, option and example, read from the live `typer` tree.

The tree is the one `diagnos --help` renders, so the reference cannot
describe a flag the binary does not have. Help text is `English · Português`
(`bilingual.split_cli_help`); examples come from each command's epilog,
where `diagnos_cli.examples` writes them as `$ <command>` lines followed by
their description — the same lines a user sees at the bottom of `--help`.

🇧🇷 `cli.json`: todo comando, opção e exemplo do `diagnos`, lidos da árvore `typer` viva.

A árvore é a mesma que o `diagnos --help` renderiza, então a referência não
consegue descrever uma flag que o binário não tem. O texto de ajuda é
`English · Português` (`bilingual.split_cli_help`); os exemplos vêm do epílogo
de cada comando, onde `diagnos_cli.examples` os escreve como linhas
`$ <comando>` seguidas da descrição — as mesmas linhas que um usuário vê no
fim do `--help`.
"""

from __future__ import annotations

from collections.abc import Iterator
from importlib.metadata import version
from typing import Any

import typer
from diagnos_cli.main import typer_app
from typer.core import TyperArgument, TyperGroup, TyperOption
from typer.main import get_command

from .bilingual import l10n_field
from .output import SCHEMA_VERSION, generated_from

PROGRAM = "diagnos"
_TYPE_NAMES = {"str": "str", "text": "str", "integer": "int", "int": "int", "boolean": "bool", "float": "float"}


def root_command() -> TyperGroup:
    """🇺🇸 The command group behind `diagnos` — the same object `--help` is rendered from.

    🇧🇷 O grupo de comandos por trás de `diagnos` — o mesmo objeto de que o `--help` é renderizado.
    """
    command = get_command(typer_app)
    assert isinstance(command, TyperGroup)
    return command


def walk(command: Any, path: list[str]) -> Iterator[tuple[list[str], Any]]:
    """🇺🇸 `(path, command)` depth-first, in the order `--help` lists them; the root is `[]`.

    🇧🇷 `(caminho, comando)` em profundidade, na ordem em que o `--help` os lista; a raiz é `[]`.
    """
    yield path, command
    if isinstance(command, TyperGroup):
        ctx = typer.Context(command, info_name=path[-1] if path else PROGRAM)
        for name in command.list_commands(ctx):
            sub = command.get_command(ctx, name)
            if sub is not None and not sub.hidden:
                yield from walk(sub, [*path, name])


def _type_name(param: Any) -> str:
    """🇺🇸 A short, language-neutral type: `str`, `int`, `bool`, `path`, or `list[…]` for repeatable ones.

    🇧🇷 Um tipo curto e neutro: `str`, `int`, `bool`, `path`, ou `list[…]` para os repetíveis.
    """
    name = "bool" if getattr(param, "is_flag", False) else _TYPE_NAMES.get(param.type.name, param.type.name)
    return f"list[{name}]" if param.multiple or param.nargs == -1 else name


def _default(param: Any) -> str | None:
    """🇺🇸 The default as text, or `None`; a hidden default (`--token`) is never written down.

    🇧🇷 O padrão como texto, ou `None`; um padrão escondido (`--token`) nunca é escrito.
    """
    value = param.default
    if getattr(param, "show_default", None) is False or value is None or callable(value):
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | tuple):
        return ", ".join(str(item) for item in value) or None
    return str(value)


def param_entry(param: TyperOption | TyperArgument) -> tuple[dict[str, Any], bool]:
    """🇺🇸 One `CliParam` of the contract, plus whether its help lacked a translation.

    🇧🇷 Um `CliParam` do contrato, mais se a ajuda dele não tinha tradução.
    """
    is_option = isinstance(param, TyperOption)
    flags = [*param.opts, *param.secondary_opts] if is_option else []
    long_flag = next((flag for flag in param.opts if flag.startswith("--")), None)
    name = long_flag[2:] if is_option and long_flag else str(param.name)
    help_text, untranslated = l10n_field(getattr(param, "help", None), cli=True)
    entry = {
        "name": name,
        "kind": "option" if is_option else "argument",
        "flags": flags,
        "type": _type_name(param),
        "required": param.required,
        "default": _default(param),
        "help": help_text,
    }
    return entry, untranslated


def examples(epilog: str | None) -> tuple[list[dict[str, Any]], bool]:
    """🇺🇸 The `$ diagnos …` lines of an epilog, each with the description on the lines under it.

    🇧🇷 As linhas `$ diagnos …` de um epílogo, cada uma com a descrição nas linhas abaixo dela.
    """
    found: list[dict[str, Any]] = []
    descriptions: list[list[str]] = []
    for line in (epilog or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("$ "):
            found.append({"command": stripped[2:].strip()})
            descriptions.append([])
        elif stripped and descriptions:
            descriptions[-1].append(stripped)
    untranslated = False
    for example, lines in zip(found, descriptions, strict=True):
        if lines:
            example["description"], missing = l10n_field(" ".join(lines), cli=True)
            untranslated = untranslated or missing
    return found, untranslated


def command_entry(path: list[str], command: Any) -> dict[str, Any]:
    """🇺🇸 One `CliCommand`: help, parameters (never `--help` itself) and examples.

    🇧🇷 Um `CliCommand`: ajuda, parâmetros (nunca o próprio `--help`) e exemplos.
    """
    help_text, untranslated = l10n_field(command.help, cli=True)
    params: list[dict[str, Any]] = []
    for param in command.params:
        if getattr(param, "hidden", False):
            continue
        entry, missing = param_entry(param)
        params.append(entry)
        untranslated = untranslated or missing
    found, missing = examples(command.epilog)
    entry_out: dict[str, Any] = {"path": path, "help": help_text, "params": params}
    if found:
        entry_out["examples"] = found
    if untranslated or missing:
        entry_out["untranslated"] = True
    return entry_out


def build() -> dict[str, Any]:
    """🇺🇸 The whole `cli.json` document. 🇧🇷 O documento `cli.json` inteiro."""
    root = root_command()
    help_text, _ = l10n_field(root.help, cli=True)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedFrom": generated_from("diagnos-cli"),
        "program": {"name": PROGRAM, "help": help_text, "version": version("diagnos-cli")},
        "commands": [command_entry(path, command) for path, command in walk(root, [])],
    }
