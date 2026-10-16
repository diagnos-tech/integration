"""🇺🇸 `diagnos session start | lock` — keep a session for the next commands, or end it.

`start` exists for the legacy `apikey-` token, whose session needs a human
approval: it starts the session agent (`diagnos.cli.agent`), approves once,
and the commands that follow reuse that session until `diagnos logout`. A
service account token needs none of that — every command opens its own
session with one signed request — but `start` works with it too.

🇧🇷 `diagnos session start | lock` — manter uma sessão para os próximos comandos, ou encerrá-la.

O `start` existe para o token legado `apikey-`, cuja sessão precisa de
aprovação humana: ele sobe o agente de sessão (`diagnos.cli.agent`), aprova
uma vez, e os comandos seguintes reaproveitam essa sessão até o
`diagnos logout`. Um token de conta de serviço não precisa de nada disso —
todo comando abre a própria sessão com uma requisição assinada — mas o
`start` funciona com ele também.
"""

from __future__ import annotations

import typer

from diagnos.cli import context
from diagnos.cli.context import CliOptions
from diagnos.cli.examples import examples
from diagnos.cli.render import get_console, get_err_console, print_json

app = typer.Typer(help="Session lifecycle · Ciclo de vida da sessão")


@app.command(
    "start",
    help="Open a session and keep it for the next commands · Abre uma sessão e a mantém para os próximos comandos",
    epilog=examples(
        (
            "diagnos session start",
            "Legacy token: a link and a code, then the agent keeps the session · Token legado: link e código, "
            "depois o agente mantém a sessão",
        ),
        ("diagnos session start --no-auto-unseal", "Do not save the session to OpenBao · Não salva no OpenBao"),
    ),
)
def start(
    ctx: typer.Context,
    auto_unseal: bool | None = typer.Option(
        None,
        "--auto-unseal/--no-auto-unseal",
        help=(
            "Save/restore the session via OpenBao (default: on for the legacy token when OPENBAO_ADDR is set, off "
            "for a service account token) · Salva/restaura a sessão via OpenBao (padrão: ligado para o token legado "
            "quando OPENBAO_ADDR está definida, desligado para um token de conta de serviço)"
        ),
    ),
) -> None:
    """🇺🇸 Unlocks (inside the agent when one could start), then prints workspace, account and granted groups.

    🇧🇷 Desbloqueia (dentro do agente quando um pôde subir), depois imprime workspace, conta e grupos concedidos.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    with context.enrollment_progress(get_err_console(opts), quiet=opts.quiet) as on_prompt:
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
    console.print("[bold green]Session open · Sessão aberta[/bold green]")
    console.print(f"  workspace_id: {result['workspace_id']}")
    console.print(f"  account_id:   {result['account_id']}")
    console.print(f"  groups · grupos: {', '.join(vault.security_groups) or '—'}")
    if context.is_hosted():
        console.print(
            "[dim]Kept in memory by the diagnos agent until `diagnos logout` or the idle timeout — next commands "
            "reuse it.\n"
            "Guardada na memória pelo agente do diagnos até `diagnos logout` ou o tempo ocioso — os próximos comandos "
            "a reutilizam.[/dim]"
        )


@app.command(
    "lock",
    help="End the session on the vault and wipe local keys · Encerra a sessão no cofre e apaga as chaves locais",
    epilog=examples(
        (
            "diagnos session lock",
            "End the session, wipe local keys and the OpenBao copy"
            " · Encerra a sessão, apaga as chaves locais e a cópia no OpenBao",
        )
    ),
)
def lock(ctx: typer.Context) -> None:
    """🇺🇸 Calls `vault.lock()` on a freshly built client.

    This process never called `unlock()` first, so there is no in-memory
    session to revoke — unless OpenBao is configured *and* holds one, the
    practical effect is clearing whatever OpenBao-persisted state exists
    (`Diagnos.lock`'s docstring: `close()` never revokes, only `lock()`
    does). That matches what a standalone `session lock` invocation can
    honestly promise without also forcing a fresh session just to tear it
    down again.

    🇧🇷 Chama `vault.lock()` numa client recém-construída.

    Este processo nunca chamou `unlock()` antes, então não existe sessão em
    memória para revogar — a menos que o OpenBao esteja configurado *e*
    guarde uma, o efeito prático é limpar o que existir persistido no
    OpenBao (docstring de `Diagnos.lock`: `close()` nunca revoga, só
    `lock()`). Isso é o que uma invocação isolada de `session lock` pode
    prometer com honestidade, sem forçar uma sessão nova só para
    derrubá-la de novo em seguida.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    vault = context.build_client(opts)
    vault.lock()
    if not opts.quiet and not opts.json_output:
        console.print("[green]Session locked · Sessão travada[/green]")
