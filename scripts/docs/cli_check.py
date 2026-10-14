"""`cli.json` against the binary: every `diagnos … --help` must say what the reference says, both ways.

`cli.json` is generated from the same `typer` tree, so a disagreement here
means the introspection itself missed something the user sees — an
option rendered but not recorded, a help text or example the generator
dropped. The help is rendered exactly as a user gets it (`CliRunner`,
rich panels, 250 columns so nothing wraps) and read panel by panel, with
the terminal styling removed: typer forces it on under `GITHUB_ACTIONS`,
and a bold escape in the middle of `--json` is not part of what the help
says.

The same map also checks the prose: every `diagnos …` command line in a
shell block of the docs must name real commands and real flags.
"""

from __future__ import annotations

import re
import shlex
from typing import Any

from typer.testing import CliRunner

from diagnos.cli.argv import hoist_global_options
from diagnos.cli.main import typer_app

from .markdown import fences

SHELLS = {"sh", "bash", "shell", "console", "zsh"}
_PANEL = re.compile(r"^╭─ (?P<title>[^─]+?) ─")
_STYLE = re.compile(r"\x1b\[[0-9;]*m")
_COMMAND_START = re.compile(r"(?:^|[|;&(`]\s*|\$\(\s*)(?:\$ )?(?P<cmd>diagnos(?=\s|$)[^|;&)`]*)")


def _normalize(text: str) -> str:
    """Returns `text` without box-drawing characters and with whitespace collapsed, so wrapping never matters."""
    return " ".join(re.sub(r"[│╭╮╰╯─]", " ", text).split())


def _panels(output: str) -> dict[str, list[str]]:
    """Returns `{panel title: first token of each row}` of a rich `--help`."""
    panels: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in output.splitlines():
        opening = _PANEL.match(line)
        if opening:
            current = panels.setdefault(opening["title"].strip(), [])
        elif line.startswith("╰"):
            current = None
        elif current is not None and line.startswith("│"):
            tokens = line.strip("│ ").split()
            tokens = tokens[1:] if tokens[:1] == ["*"] else tokens
            if tokens and not line.startswith("│     "):
                current.append(tokens[0])
    return panels


def help_problems(document: dict[str, Any]) -> list[str]:
    """Returns one line per disagreement between `diagnos <path> --help` and its `cli.json` entry.

    Args:
        document: The parsed `cli.json`. Each of its commands is rendered with `--help` and compared both ways:
            what the reference lists must be shown, and what is shown must be listed.
    """
    runner = CliRunner()
    problems: list[str] = []
    commands = document["commands"]
    for command in commands:
        path = command["path"]
        where = f"cli.json: diagnos {' '.join(path)}".rstrip()
        result = runner.invoke(typer_app, [*path, "--help"], env={"COLUMNS": "250", "NO_COLOR": "1"})
        if result.exit_code != 0:
            problems.append(f"{where}: --help exited {result.exit_code}")
            continue
        output = _STYLE.sub("", result.output)
        text, panels = _normalize(output), _panels(output)
        # Both locales hold the same English text (`l10n.l10n_field`), so `en` is the one `--help` must show.
        expected: list[str] = [command["help"]["en"]]
        for param in command["params"]:
            expected += [*param["flags"], param["help"]["en"]]
            if param["kind"] == "argument":
                expected.append(param["name"])
        expected += [example["command"] for example in command.get("examples", [])]
        problems += [f"{where}: --help lacks {item!r}" for item in expected if _normalize(item) not in text]
        options = {flag for p in command["params"] for flag in p["flags"] if p["kind"] == "option"}
        shown = set(panels.get("Options", [])) - {"--help"}
        problems += [f"{where}: --help shows {flag!r}, cli.json does not" for flag in sorted(shown - options)]
        children = {c["path"][-1] for c in commands if len(c["path"]) == len(path) + 1 and c["path"][:-1] == path}
        listed = set(panels.get("Commands", []))
        problems += [f"{where}: subcommand {name!r} missing from cli.json" for name in sorted(listed - children)]
        problems += [f"{where}: subcommand {name!r} missing from --help" for name in sorted(children - listed)]
    return problems


def command_lines(text: str) -> list[tuple[int, str]]:
    """Returns `(line, command)` for every `diagnos …` invocation in a shell block, continuations joined.

    Args:
        text: The Markdown of a page. Only fences whose language is in `SHELLS` are read.
    """
    found: list[tuple[int, str]] = []
    for fence in fences(text):
        if fence.language not in SHELLS:
            continue
        logical, start = "", fence.line
        for offset, raw in enumerate(fence.body.splitlines()):
            if not logical:
                start = fence.line + offset
            logical += raw.rstrip("\\").rstrip() + " " if raw.rstrip().endswith("\\") else raw
            if raw.rstrip().endswith("\\"):
                continue
            found += [(start, match["cmd"].strip()) for match in _COMMAND_START.finditer(logical.strip())]
            logical = ""
    return found


def usage_problem(line: str, document: dict[str, Any]) -> str | None:
    """Returns why `line` is not a valid `diagnos` invocation (unknown command or flag), or `None`.

    Global options count wherever they are on the line, moved to the front
    the way the binary moves them (`diagnos.cli.argv`). Option values are
    skipped by the option's type, so a positional value is never mistaken
    for a subcommand.

    Args:
        line: One `diagnos …` command line, as `command_lines` yields it.
        document: The parsed `cli.json`, whose command tree the line is checked against.
    """
    try:
        tokens = hoist_global_options(shlex.split(line, comments=True)[1:])
    except ValueError as error:
        return f"cannot parse ({error})"
    by_path = {tuple(c["path"]): c for c in document["commands"]}
    path: tuple[str, ...] = ()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        params = by_path[path]["params"]
        if token.startswith("-") and token not in ("-", "--"):
            flag = token.split("=", 1)[0]
            match = next((p for p in params if flag in p["flags"]), None)
            if match is None and flag != "--help":
                return f"unknown option {flag!r} for 'diagnos {' '.join(path)}'"
            takes_value = match is not None and match["type"] != "bool" and "=" not in token
            index += 2 if takes_value else 1
            continue
        if (*path, token) in by_path:
            path = (*path, token)
        elif any(len(key) == len(path) + 1 and key[:-1] == path for key in by_path):
            return f"unknown command 'diagnos {' '.join((*path, token))}'"
        index += 1
    return None
