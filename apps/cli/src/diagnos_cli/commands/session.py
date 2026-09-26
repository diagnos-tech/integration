"""🇺🇸 `diagnos session lock` — ends the session, best-effort server-side, and always wipes local key material.

🇧🇷 `diagnos session lock` — encerra a sessão, best-effort do lado do
servidor, e sempre apaga o material de chave local.
"""

from __future__ import annotations

import typer

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.examples import examples
from diagnos_cli.render import get_console

app = typer.Typer(help="Session lifecycle · Ciclo de vida da sessão")


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
    honestly promise without also forcing a fresh enrollment just to tear
    it down again.

    🇧🇷 Chama `vault.lock()` numa client recém-construída.

    Este processo nunca chamou `unlock()` antes, então não existe sessão em
    memória para revogar — a menos que o OpenBao esteja configurado *e*
    guarde uma, o efeito prático é limpar o que existir persistido no
    OpenBao (docstring de `Diagnos.lock`: `close()` nunca revoga, só
    `lock()`). Isso é o que uma invocação isolada de `session lock` pode
    prometer com honestidade, sem forçar um enrollment novo só para
    derrubá-lo de novo em seguida.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    vault = context.build_client(opts)
    vault.lock()
    if not opts.quiet and not opts.json_output:
        console.print("[green]Session locked · Sessão travada[/green]")
