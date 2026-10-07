"""🇺🇸 The flag verbs — archive, unarchive, delete, restore — as `patients` and `exams` both run them.

None of them writes a version: each flips one flag on the vault and answers
the updated index. Unlocking, the enrollment prompt and the rendering are
the same for all eight commands, so they live here once.

🇧🇷 Os verbos de flag — archive, unarchive, delete, restore — como `patients` e `exams` os rodam.

Nenhum grava versão: cada um troca uma flag no cofre e responde o índice
atualizado. O unlock, o prompt de enrollment e a renderização são os mesmos
nos oito comandos, então moram aqui uma vez só.
"""

from __future__ import annotations

from collections.abc import Callable

import typer
from diagnos import Diagnos, DocumentIndex

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.render import get_console, get_err_console, render_document_index


def flip(ctx: typer.Context, verb: Callable[[Diagnos], DocumentIndex]) -> None:
    """🇺🇸 Unlocks, runs one flag verb on the vault and renders the index it answers.

    🇧🇷 Desbloqueia, roda um verbo de flag no cofre e renderiza o índice que ele responde.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        index = verb(context.build_client(opts, on_prompt=on_prompt))
    render_document_index(console, index, json_output=opts.json_output)
