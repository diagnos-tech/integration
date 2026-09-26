"""🇺🇸 `diagnos logout` — revoke the kept session and stop the agent.

Inside the agent it asks the agent to lock the one session (revoked on the
vault, keys wiped) and exit; the agent does both before this command's
reply reaches the terminal. Run in-process there is
no kept session to end — each command's session already died with it — so
it just says so.

🇧🇷 `diagnos logout` — revoga a sessão guardada e para o agente.

Dentro do agente, pede ao agente para travar a única sessão (revogada no
cofre, chaves apagadas) e sair; o agente faz os dois antes de a resposta
deste comando chegar ao terminal. Rodando no próprio processo
não há sessão guardada para encerrar — a sessão de cada comando já morreu
com ele — então só avisa isso.
"""

from __future__ import annotations

import typer

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.render import get_console, print_json


def logout(ctx: typer.Context) -> None:
    """🇺🇸 Locks the agent's session and stops it; without an agent, reports there was nothing to end.

    🇧🇷 Trava a sessão do agente e o para; sem agente, avisa que não havia nada a encerrar.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    hosted = context.is_hosted()
    if hosted:
        context.request_agent_stop()
    if opts.json_output:
        print_json({"logged_out": hosted})
    elif not opts.quiet:
        message = (
            "[green]Logged out · Sessão encerrada[/green]"
            if hosted
            else "[dim]No session kept for this token · Nenhuma sessão guardada para este token[/dim]"
        )
        console.print(message)
