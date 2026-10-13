"""🇺🇸 How the base writes: plain lines, color only on a real terminal, JSON for scripts — standard library only.

Color follows the conventions people already set once for every tool:
`NO_COLOR` (https://no-color.org), a `dumb` terminal, or output that is not
a terminal turn it off. Text sticks to characters every Windows code page
can encode, so a redirected `diagnos version > out.txt` never crashes on a
check mark.

🇧🇷 Como a base escreve: linhas simples, cor só num terminal de verdade, JSON para scripts — só biblioteca padrão.

A cor segue as convenções que as pessoas já configuram uma vez para toda
ferramenta: `NO_COLOR` (https://no-color.org), um terminal `dumb`, ou uma
saída que não é terminal a desligam. O texto fica em caracteres que toda
página de código do Windows codifica, para um `diagnos version > out.txt`
redirecionado nunca quebrar num sinal de visto.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TextIO

_RESET = "\x1b[0m"
_CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "cyan": "36"}


def color_wanted(stream: TextIO, env: Mapping[str, str] = os.environ) -> bool:
    """🇺🇸 Whether ANSI color belongs on `stream`: a terminal, `NO_COLOR` unset, not `TERM=dumb`, VT-capable.

    Legacy Windows consoles print escape codes literally; Windows Terminal
    (`WT_SESSION`) and terminals that set `TERM` (Git Bash, MSYS) render them.

    🇧🇷 Se cor ANSI cabe em `stream`: um terminal, `NO_COLOR` não definida, não `TERM=dumb`, com suporte a VT.

    Consoles legados do Windows imprimem os códigos literalmente; o Windows
    Terminal (`WT_SESSION`) e terminais que definem `TERM` (Git Bash, MSYS)
    os renderizam.
    """
    if env.get("NO_COLOR") or env.get("TERM") == "dumb" or not stream.isatty():
        return False
    return sys.platform != "win32" or "WT_SESSION" in env or "TERM" in env


@dataclass(frozen=True)
class Output:
    """🇺🇸 Where and how one command writes: the two streams, JSON or text, color or not.

    🇧🇷 Onde e como um comando escreve: os dois streams, JSON ou texto, com cor ou sem.
    """

    stdout: TextIO = field(default_factory=lambda: sys.stdout)
    stderr: TextIO = field(default_factory=lambda: sys.stderr)
    json_output: bool = False
    color: bool = False

    @classmethod
    def terminal(cls, *, json_output: bool = False, no_color: bool = False) -> Output:
        """🇺🇸 The process's own streams, colored when `stdout` is a capable terminal.

        🇧🇷 Os streams do próprio processo, coloridos quando o `stdout` é um terminal capaz.
        """
        return cls(json_output=json_output, color=not no_color and color_wanted(sys.stdout))

    def line(self, text: str = "") -> None:
        """🇺🇸 One line on `stdout`. 🇧🇷 Uma linha no `stdout`."""
        self.stdout.write(f"{text}\n")
        self.stdout.flush()

    def error(self, text: str) -> None:
        """🇺🇸 One line on `stderr`. 🇧🇷 Uma linha no `stderr`."""
        self.stderr.write(f"{text}\n")
        self.stderr.flush()

    def data(self, value: object) -> None:
        """🇺🇸 `value` as indented JSON on `stdout` — the whole output of a `--json` run.

        🇧🇷 `value` como JSON indentado no `stdout` — a saída inteira de uma execução `--json`.
        """
        self.line(json.dumps(value, indent=2, ensure_ascii=False))

    def style(self, text: str, *styles: str) -> str:
        """🇺🇸 `text` wrapped in the named ANSI styles, or unchanged without color.

        🇧🇷 `text` envolvido nos estilos ANSI nomeados, ou intacto sem cor.
        """
        if not self.color or not styles:
            return text
        return f"\x1b[{';'.join(_CODES[name] for name in styles)}m{text}{_RESET}"


def table(rows: Sequence[tuple[str, ...]], *, indent: int = 2) -> list[str]:
    """🇺🇸 `rows` as aligned columns (the last one left ragged), one string per row.

    🇧🇷 `rows` como colunas alinhadas (a última solta), uma string por linha.
    """
    if not rows:
        return []
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]) - 1)]
    pad = " " * indent
    return [
        pad + "  ".join([*(cell.ljust(width) for cell, width in zip(row, widths, strict=False)), row[-1]]).rstrip()
        for row in rows
    ]
