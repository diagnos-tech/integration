"""`cli.json`: every `diagnos` command, option and example, read from the live `typer` tree.

The tree is the one `diagnos --help` renders, so the reference cannot
describe a flag the binary does not have. Help text is plain English and goes
to both locales (`l10n.l10n_field`); examples come from each command's
epilog, where `diagnos.cli.examples` writes them as `$ <command>` lines
followed by their description — the same lines a user sees at the bottom of
`--help`.
"""

from __future__ import annotations

from collections.abc import Iterator
from importlib.metadata import version
from typing import Any

import typer
from typer.core import TyperArgument, TyperGroup, TyperOption
from typer.main import get_command

from diagnos.cli.main import typer_app

from .l10n import l10n_field
from .output import SCHEMA_VERSION, generated_from

PROGRAM = "diagnos"
_TYPE_NAMES = {"str": "str", "text": "str", "integer": "int", "int": "int", "boolean": "bool", "float": "float"}


def root_command() -> TyperGroup:
    """Returns the command group behind `diagnos`, the same object `--help` is rendered from."""
    command = get_command(typer_app)
    assert isinstance(command, TyperGroup)
    return command


def walk(command: Any, path: list[str]) -> Iterator[tuple[list[str], Any]]:
    """Yields `(path, command)` depth-first, in the order `--help` lists them; the root is `[]`."""
    yield path, command
    if isinstance(command, TyperGroup):
        ctx = typer.Context(command, info_name=path[-1] if path else PROGRAM)
        for name in command.list_commands(ctx):
            sub = command.get_command(ctx, name)
            if sub is not None and not sub.hidden:
                yield from walk(sub, [*path, name])


def _type_name(param: Any) -> str:
    """Returns a short, language-neutral type: `str`, `int`, `bool`, `path`, or `list[…]` for repeatable ones."""
    name = "bool" if getattr(param, "is_flag", False) else _TYPE_NAMES.get(param.type.name, param.type.name)
    return f"list[{name}]" if param.multiple or param.nargs == -1 else name


def _default(param: Any) -> str | None:
    """Returns the default as text, or `None`; a hidden default (`--token`) is never written down."""
    value = param.default
    if getattr(param, "show_default", None) is False or value is None or callable(value):
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | tuple):
        return ", ".join(str(item) for item in value) or None
    return str(value)


def param_entry(param: TyperOption | TyperArgument) -> dict[str, Any]:
    """Returns one `CliParam` of the contract."""
    is_option = isinstance(param, TyperOption)
    flags = [*param.opts, *param.secondary_opts] if is_option else []
    long_flag = next((flag for flag in param.opts if flag.startswith("--")), None)
    name = long_flag[2:] if is_option and long_flag else str(param.name)
    return {
        "name": name,
        "kind": "option" if is_option else "argument",
        "flags": flags,
        "type": _type_name(param),
        "required": param.required,
        "default": _default(param),
        "help": l10n_field(getattr(param, "help", None)),
    }


def examples(epilog: str | None) -> list[dict[str, Any]]:
    """Returns the `$ diagnos …` lines of an epilog, each with the description on the lines under it."""
    found: list[dict[str, Any]] = []
    descriptions: list[list[str]] = []
    for line in (epilog or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("$ "):
            found.append({"command": stripped[2:].strip()})
            descriptions.append([])
        elif stripped and descriptions:
            descriptions[-1].append(stripped)
    for example, lines in zip(found, descriptions, strict=True):
        if lines:
            example["description"] = l10n_field(" ".join(lines))
    return found


def command_entry(path: list[str], command: Any) -> dict[str, Any]:
    """Returns one `CliCommand`: help, parameters (never `--help` itself) and examples."""
    params = [param_entry(param) for param in command.params if not getattr(param, "hidden", False)]
    entry: dict[str, Any] = {"path": path, "help": l10n_field(command.help), "params": params}
    found = examples(command.epilog)
    if found:
        entry["examples"] = found
    return entry


def build() -> dict[str, Any]:
    """Returns the whole `cli.json` document."""
    root = root_command()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedFrom": generated_from("diagnos"),
        "program": {"name": PROGRAM, "help": l10n_field(root.help), "version": version("diagnos")},
        "commands": [command_entry(path, command) for path, command in walk(root, [])],
    }
