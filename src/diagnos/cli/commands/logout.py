"""🇺🇸 `diagnos logout` — forget the stored token (keyring and OpenBao) and stop a legacy session agent.

What `diagnos login` stored is deleted from the system keyring and, when
`OPENBAO_ADDR` is configured, from OpenBao. `DIAGNOS_TOKEN` is the shell's,
not ours to clear, so it is only named if it is still set. Run inside the
legacy session agent (`diagnos session start`), it also asks the agent to
lock its session and exit.

🇧🇷 `diagnos logout` — esquece o token guardado (chaveiro e OpenBao) e para um agente de sessão legado.

O que o `diagnos login` guardou é apagado do chaveiro do sistema e, quando
`OPENBAO_ADDR` está configurada, do OpenBao. O `DIAGNOS_TOKEN` é do shell,
não cabe a nós limpá-lo, então só é citado se continuar definido. Rodando
dentro do agente de sessão legado (`diagnos session start`), também pede ao
agente para travar a sessão e sair.
"""

from __future__ import annotations

import os

import typer

from diagnos import Settings, forget_token
from diagnos.cli import context
from diagnos.cli.context import CliOptions
from diagnos.cli.render import get_console, print_json


def logout(ctx: typer.Context) -> None:
    """🇺🇸 Deletes the stored token and stops the agent, then says what was removed.

    🇧🇷 Apaga o token guardado e para o agente, depois diz o que foi removido.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    removed = forget_token(settings=Settings.without_token(context.environment(opts)))
    hosted = context.is_hosted()
    if hosted:
        context.request_agent_stop()
    still_set = bool(os.environ.get("DIAGNOS_TOKEN"))
    if opts.json_output:
        print_json({"removed_from": removed, "agent_stopped": hosted, "diagnos_token_still_set": still_set})
        return
    if opts.quiet:
        return
    for where in removed:
        console.print(f"[green]Token removed from · Token removido de:[/green] {where}")
    if not removed:
        console.print("[dim]No stored token · Nenhum token guardado[/dim]")
    if hosted:
        console.print("[green]Session agent stopped · Agente de sessão parado[/green]")
    if still_set:
        console.print(
            "[yellow]DIAGNOS_TOKEN is still set in this shell · DIAGNOS_TOKEN continua definida neste shell[/yellow]"
        )
