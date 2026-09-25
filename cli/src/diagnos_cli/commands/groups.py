"""🇺🇸 `diagnos groups` — the security groups this enrollment holds a DEK for.

🇧🇷 `diagnos groups` — os security groups para os quais este enrollment tem uma DEK.
"""

from __future__ import annotations

import typer

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.render import get_console, get_err_console, print_json


def groups(ctx: typer.Context) -> None:
    """🇺🇸 Unlocks (if needed) and lists `vault.security_groups` — empty only means none were granted.

    🇧🇷 Desbloqueia (se preciso) e lista `vault.security_groups` — vazio só significa que nenhum foi concedido.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        vault.unlock()
        security_groups = vault.security_groups

    if opts.json_output:
        print_json({"security_groups": security_groups})
        return
    if not security_groups:
        console.print("[dim]No security groups granted · Nenhum security group concedido[/dim]")
        return
    for security_group_id in security_groups:
        console.print(security_group_id)
