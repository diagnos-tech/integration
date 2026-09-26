"""🇺🇸 Which security group a write goes to: `--group`, `DIAGNOS_GROUP`, a hint, or the session's only group.

`patients create`, `exams create`, `files upload` and `files mkdir` share
this rule. It never guesses between several groups: sealing under the wrong
one hands the record to the wrong team, so an ambiguous case stops and
lists the choices.

🇧🇷 Para qual security group uma gravação vai: `--group`, `DIAGNOS_GROUP`, uma dica, ou o único grupo da sessão.

`patients create`, `exams create`, `files upload` e `files mkdir`
compartilham esta regra. Ela nunca chuta entre vários grupos: selar sob o
errado entrega o registro à equipe errada, então um caso ambíguo para e
lista as opções.
"""

from __future__ import annotations

from typing import Any

import typer
from diagnos import Diagnos
from rich.console import Console
from rich.markup import escape

# 🇺🇸 Where a command that writes finds its security group when `--group` is not given.
# 🇧🇷 Onde um comando que grava acha o security group quando `--group` não é passado.
GROUP_ENV_VAR = "DIAGNOS_GROUP"


def group_option() -> Any:
    """🇺🇸 The `--group` of commands that write: optional, read from `DIAGNOS_GROUP`, else inferred.

    Most service accounts are approved for a single group, and typing it on
    every `create`/`upload` is noise; `resolve_group` fills it in and says
    which group it picked.

    🇧🇷 O `--group` dos comandos que gravam: opcional, lido de `DIAGNOS_GROUP`, senão inferido.

    A maioria das service accounts é aprovada para um único grupo, e
    digitá-lo em todo `create`/`upload` é ruído; `resolve_group` o preenche e
    diz qual grupo escolheu.
    """
    return typer.Option(
        None,
        "--group",
        "-g",
        envvar=GROUP_ENV_VAR,
        show_envvar=True,
        help="Security group to seal under (default: the only one this session holds) · "
        "Grupo sob o qual selar (padrão: o único que esta sessão tem)",
    )


def resolve_group(
    vault: Diagnos,
    group: str | None,
    *,
    err_console: Console,
    quiet: bool,
    inferred: tuple[str, str] | None = None,
) -> str:
    """🇺🇸 `--group`/`DIAGNOS_GROUP` as given; else `inferred` (a group and why); else the session's only group.

    Anything ambiguous is a usage error that lists the choices — never a
    guess: sealing under the wrong group hands the record to the wrong team.

    🇧🇷 `--group`/`DIAGNOS_GROUP` como veio; senão `inferred` (um grupo e o porquê); senão o único grupo da sessão.

    Qualquer ambiguidade é erro de uso que lista as opções — nunca um
    chute: selar sob o grupo errado entrega o registro à equipe errada.
    """
    if group:
        return group
    if inferred is not None:
        chosen, reason = inferred
    else:
        vault.unlock()
        granted = vault.security_groups
        if len(granted) != 1:
            raise typer.BadParameter(_no_single_group(granted), param_hint="--group")
        chosen, reason = granted[0], "the only group this session holds · o único grupo desta sessão"
    if not quiet:
        err_console.print(f"[dim]group · grupo: {escape(chosen)} ({reason})[/dim]", highlight=False)
    return chosen


def _no_single_group(granted: list[str]) -> str:
    """🇺🇸 Why no group could be picked, and what to do. 🇧🇷 Por que nenhum grupo pôde ser escolhido, e o que fazer."""
    if not granted:
        return (
            "this session holds no security group key — ask a workspace admin to approve an enrollment that "
            "includes one · esta sessão não tem chave de nenhum security group — peça a um admin do workspace "
            "que aprove um enrollment que inclua um"
        )
    choices = ", ".join(granted)
    return (
        f"this session holds {len(granted)} groups; pick one with --group or {GROUP_ENV_VAR}: {choices} · "
        f"esta sessão tem {len(granted)} grupos; escolha um com --group ou {GROUP_ENV_VAR}: {choices}"
    )
