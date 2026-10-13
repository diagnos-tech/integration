"""🇺🇸 Plans and how they run: every step shown first, confirmed once, then run in order until one fails.

Nothing here builds a shell command line. A step's argv starts with an
absolute path resolved once (`tools.find`), so a later change to `PATH` — or
a file named `uv` in the current folder — cannot swap the program between
what was shown and what runs. The confirmation is skipped only by an
explicit `--yes`; without a terminal to ask on, nothing runs.

🇧🇷 Planos e como rodam: todo passo mostrado antes, confirmado uma vez, e rodado em ordem até um falhar.

Nada aqui monta uma linha de comando de shell. O argv de um passo começa com
um caminho absoluto resolvido uma vez (`tools.find`), então uma mudança
posterior no `PATH` — ou um arquivo chamado `uv` na pasta atual — não troca
o programa entre o que foi mostrado e o que roda. A confirmação só é pulada
por um `--yes` explícito; sem terminal para perguntar, nada roda.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from ..exit_codes import EXIT_FAILED, EXIT_OK, EXIT_USAGE
from ..output import Output


@dataclass(frozen=True)
class Step:
    """🇺🇸 One thing `setup` does: what it is for, the command a person would type, and how to do it.

    🇧🇷 Uma coisa que o `setup` faz: para que serve, o comando que uma pessoa digitaria, e como fazer.
    """

    summary: str
    shown: str
    action: Callable[[Output], int]


@dataclass(frozen=True)
class Plan:
    """🇺🇸 A target's steps, plus the lines that tell what to do once they all succeed.

    🇧🇷 Os passos de um alvo, mais as linhas que dizem o que fazer quando todos dão certo.
    """

    title: str
    steps: tuple[Step, ...]
    after: tuple[str, ...] = field(default=())


def shown(argv: Sequence[str]) -> str:
    """🇺🇸 `argv` as a person would type it: the program by its bare name, the rest quoted for their shell.

    🇧🇷 `argv` como uma pessoa digitaria: o programa pelo nome, o resto entre aspas para o shell dela.
    """
    words = [Path(argv[0]).stem, *argv[1:]]
    return subprocess.list2cmdline(words) if os.name == "nt" else shlex.join(words)


def command(summary: str, argv: Sequence[str]) -> Step:
    """🇺🇸 A step that runs `argv` with this terminal's input and output, and returns its exit code.

    🇧🇷 Um passo que roda `argv` com a entrada e a saída deste terminal, e devolve o código de saída.
    """
    frozen = tuple(argv)

    def action(_out: Output) -> int:
        """🇺🇸 Runs `frozen`, inheriting the terminal. 🇧🇷 Roda `frozen`, herdando o terminal."""
        return subprocess.run(frozen, check=False).returncode  # noqa: S603 — argv list, absolute path from `find`

    return Step(summary, shown(frozen), action)


def show(plan: Plan, out: Output) -> None:
    """🇺🇸 Prints the plan: numbered steps, each with the command it runs.

    🇧🇷 Imprime o plano: passos numerados, cada um com o comando que roda.
    """
    out.line(out.style(plan.title, "bold"))
    for number, step in enumerate(plan.steps, start=1):
        out.line(f"  {number}. {step.summary}")
        out.line(out.style(f"     $ {step.shown}", "cyan"))


def confirm(out: Output, stdin: TextIO) -> bool:
    """🇺🇸 Asks once and defaults to no: only `y`/`yes` or `s`/`sim` agree — Enter alone runs nothing.

    🇧🇷 Pergunta uma vez e o padrão é não: só `y`/`yes` ou `s`/`sim` concordam — Enter sozinho não roda nada.
    """
    out.stdout.write("Run it? · Executar? [y/N] ")
    out.stdout.flush()
    return stdin.readline().strip().lower() in ("y", "yes", "s", "sim")


def carry_out(plan: Plan, out: Output, *, assume_yes: bool, dry_run: bool, stdin: TextIO) -> int:
    """🇺🇸 Shows `plan`, asks (unless `--yes`), runs it; `EXIT_FAILED` at the first step that fails.

    The failed program's own exit code is printed, not returned: `uv` or
    `docker` exiting `2` must not read as this command's usage error.

    🇧🇷 Mostra o `plan`, pergunta (salvo `--yes`), roda; `EXIT_FAILED` no primeiro passo que falhar.

    O código de saída do programa que falhou é impresso, não devolvido: `uv`
    ou `docker` saindo com `2` não pode parecer erro de uso deste comando.
    """
    show(plan, out)
    if dry_run:
        return EXIT_OK
    if not assume_yes:
        if not stdin.isatty():
            out.error("Nothing ran: no terminal to confirm on. Add --yes · Nada rodou: sem terminal. Use --yes")
            return EXIT_USAGE
        if not confirm(out, stdin):
            out.line("Nothing ran · Nada rodou.")
            return EXIT_FAILED
    for number, step in enumerate(plan.steps, start=1):
        out.line(out.style(f"[{number}/{len(plan.steps)}] {step.summary}", "bold"))
        code = step.action(out)
        if code != EXIT_OK:
            out.error(out.style(f"Step {number} failed (exit {code}) · O passo {number} falhou (saída {code})", "red"))
            return EXIT_FAILED
    out.line(out.style("Done · Pronto.", "green"))
    if plan.after:
        out.line()
        out.line(out.style("Next · Próximo:", "bold"))
        for line in plan.after:
            out.line(f"  {line}")
    return EXIT_OK
