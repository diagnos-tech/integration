"""🇺🇸 `cli.json` against the binary: every `diagnos … --help` must say what the reference says, both ways.

`cli.json` is generated from the same `typer` tree, so a disagreement here
means the introspection itself missed something the user sees — an
option rendered but not recorded, a help text or example the generator
dropped. The help is rendered exactly as a user gets it (`CliRunner`,
rich panels, 250 columns so nothing wraps) and read panel by panel.

The same map also checks the prose: every `diagnos …` command line in a
shell block of the docs must name real commands and real flags.

🇧🇷 O `cli.json` contra o binário: todo `diagnos … --help` precisa dizer o que a referência diz, nos dois sentidos.

O `cli.json` é gerado da mesma árvore `typer`, então uma divergência aqui
significa que a própria introspecção perdeu algo que o usuário vê — uma
opção renderizada mas não registrada, um texto de ajuda ou exemplo que o
gerador descartou. A ajuda é renderizada exatamente como o usuário a recebe
(`CliRunner`, painéis rich, 250 colunas para nada quebrar) e lida painel a
painel.

O mesmo mapa confere a prosa: toda linha de comando `diagnos …` num bloco
de shell da doc precisa nomear comandos e flags de verdade.
"""

from __future__ import annotations

import re
import shlex
from typing import Any

from diagnos_cli.main import typer_app
from typer.testing import CliRunner

from .markdown import fences

SHELLS = {"sh", "bash", "shell", "console", "zsh"}
_PANEL = re.compile(r"^╭─ (?P<title>[^─]+?) ─")
_COMMAND_START = re.compile(r"(?:^|[|;&(`]\s*|\$\(\s*)(?:\$ )?(?P<cmd>diagnos(?=\s|$)[^|;&)`]*)")


def _normalize(text: str) -> str:
    """🇺🇸 Box drawing removed and whitespace collapsed, so wrapping never matters. 🇧🇷 Sem caixas, espaços colapsados."""
    return " ".join(re.sub(r"[│╭╮╰╯─]", " ", text).split())


def _panels(output: str) -> dict[str, list[str]]:
    """🇺🇸 `{panel title: first token of each row}` of a rich `--help`. 🇧🇷 `{título: primeiro token de cada linha}`."""
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
    """🇺🇸 One line per disagreement between `diagnos <path> --help` and its `cli.json` entry.

    🇧🇷 Uma linha por divergência entre `diagnos <caminho> --help` e a entrada dele no `cli.json`.
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
        text, panels = _normalize(result.output), _panels(result.output)
        expected: list[str] = [command["help"]["en"], command["help"]["pt-br"]]
        for param in command["params"]:
            expected += [*param["flags"], param["help"]["en"], param["help"]["pt-br"]]
            if param["kind"] == "argument":
                expected.append(param["name"])
        expected += [example["command"] for example in command.get("examples", [])]
        problems += [
            f"{where}: --help lacks · não mostra {item!r}" for item in expected if _normalize(item) not in text
        ]
        options = {flag for p in command["params"] for flag in p["flags"] if p["kind"] == "option"}
        shown = set(panels.get("Options", [])) - {"--help"}
        problems += [f"{where}: --help shows {flag!r}, cli.json does not" for flag in sorted(shown - options)]
        children = {c["path"][-1] for c in commands if len(c["path"]) == len(path) + 1 and c["path"][:-1] == path}
        listed = set(panels.get("Commands", []))
        problems += [f"{where}: subcommand {name!r} missing from cli.json" for name in sorted(listed - children)]
        problems += [f"{where}: subcommand {name!r} missing from --help" for name in sorted(children - listed)]
    return problems


def command_lines(text: str) -> list[tuple[int, str]]:
    """🇺🇸 `(line, command)` for every `diagnos …` invocation in a shell block, continuations joined.

    🇧🇷 `(linha, comando)` de toda invocação `diagnos …` num bloco de shell, com continuações juntadas.
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
    """🇺🇸 Why `line` is not a valid `diagnos` invocation (unknown command or flag), or `None`.

    Option values are skipped by the option's type, so a positional value is
    never mistaken for a subcommand.

    🇧🇷 Por que `line` não é uma invocação válida do `diagnos` (comando ou flag desconhecida), ou `None`.

    Valores de opção são pulados pelo tipo da opção, então um valor
    posicional nunca é confundido com um subcomando.
    """
    try:
        tokens = shlex.split(line, comments=True)[1:]
    except ValueError as error:
        return f"cannot parse · não interpretável ({error})"
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
                return f"unknown option {flag!r} for · opção desconhecida para 'diagnos {' '.join(path)}'"
            takes_value = match is not None and match["type"] != "bool" and "=" not in token
            index += 2 if takes_value else 1
            continue
        if (*path, token) in by_path:
            path = (*path, token)
        elif any(len(key) == len(path) + 1 and key[:-1] == path for key in by_path):
            return f"unknown command · comando desconhecido 'diagnos {' '.join((*path, token))}'"
        index += 1
    return None
