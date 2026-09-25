"""🇺🇸 `diagnos login` — runs enrollment on purpose, to validate a token and show what it was granted.

`unlock()` is idempotent and lazy (`apps/sdk/README.md`): every other command
would enroll on its own the moment it touched `vault.patients`/`exams`/
`drives`. This command exists for the case where a human wants to *see* the
approval happen — workspace, service account and granted groups — without
also running a real query. Without OpenBao configured, this session dies
with the process; the next invocation enrolls again, by design (see
`README.md`'s "OpenBao for servers" section).

🇧🇷 `diagnos login` — faz enrollment de propósito, para validar um token e
mostrar o que foi concedido.

`unlock()` é idempotente e preguiçoso (`apps/sdk/README.md`): todo outro comando
já faria enrollment sozinho no primeiro toque em
`vault.patients`/`exams`/`drives`. Este comando existe para o caso em que
uma pessoa quer *ver* a aprovação acontecer — workspace, service account e
grupos concedidos — sem também rodar uma consulta de verdade. Sem OpenBao
configurado, esta sessão morre com o processo; a próxima invocação faz
enrollment de novo, de propósito (ver a seção "OpenBao para servidores" do
`README.md`).
"""

from __future__ import annotations

import typer

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.render import get_console, get_err_console, print_json


def login(
    ctx: typer.Context,
    auto_unseal: bool | None = typer.Option(
        None,
        "--auto-unseal/--no-auto-unseal",
        help=(
            "Save/restore the session via OpenBao · Salva/restaura a sessão via OpenBao "
            "(default · padrão: on iff OPENBAO_ADDR is set · ligado se OPENBAO_ADDR estiver definida)"
        ),
    ),
) -> None:
    """🇺🇸 Enrolls (or restores from OpenBao), then prints workspace, account and granted groups.

    🇧🇷 Faz enrollment (ou restaura do OpenBao), depois imprime workspace, conta e grupos concedidos.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    err_console = get_err_console(opts)
    with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt, auto_unseal=auto_unseal)
        vault.unlock()

    result = {
        "workspace_id": vault.workspace_id,
        "account_id": vault.account_id,
        "security_groups": vault.security_groups,
    }
    if opts.json_output:
        print_json(result)
        return
    console.print("[bold green]Enrolled · Sessão estabelecida[/bold green]")
    console.print(f"  workspace_id: {result['workspace_id']}")
    console.print(f"  account_id:   {result['account_id']}")
    console.print(f"  groups · grupos: {', '.join(result['security_groups']) or '—'}")
