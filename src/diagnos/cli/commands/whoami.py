"""🇺🇸 `diagnos whoami` — which token this machine uses, proven against the vault, and what it was granted.

It opens a session (`Diagnos.whoami`): that only works when the vault
verified both signatures and the key is not revoked, so a green `whoami`
means the next command will authenticate. Where the token came from
(`DIAGNOS_TOKEN`, the keyring, OpenBao) is part of the answer — the usual
surprise is an old `DIAGNOS_TOKEN` shadowing a newer stored one.

🇧🇷 `diagnos whoami` — qual token esta máquina usa, provado contra o cofre, e o que ele recebeu.

Abre uma sessão (`Diagnos.whoami`): isso só funciona quando o cofre verificou
as duas assinaturas e a chave não está revogada, então um `whoami` verde
significa que o próximo comando vai autenticar. De onde o token veio
(`DIAGNOS_TOKEN`, o chaveiro, o OpenBao) faz parte da resposta — a surpresa
comum é um `DIAGNOS_TOKEN` velho escondendo um guardado mais novo.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import typer

from diagnos.cli import context
from diagnos.cli.context import CliOptions
from diagnos.cli.render import get_console, get_err_console, print_json


def whoami(ctx: typer.Context) -> None:
    """🇺🇸 Proves the token with a session and prints identity, source, groups and session expiry.

    🇧🇷 Prova o token com uma sessão e imprime identidade, origem, grupos e validade da sessão.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    with context.enrollment_progress(get_err_console(opts), quiet=opts.quiet) as on_prompt:
        vault = context.build_client(opts, on_prompt=on_prompt)
        who = vault.whoami()
    if opts.json_output:
        print_json(dataclasses.asdict(who))
        return
    expires = datetime.fromtimestamp(who.session_expires_at, UTC).isoformat(timespec="seconds")
    console.print(f"  identity · identidade:   {who.identity or who.key_id}")
    console.print(f"  workspace_id:            {who.workspace_id}")
    console.print(f"  token:                   {who.token_kind} — {who.token_source}")
    console.print(f"  groups · grupos:         {', '.join(who.security_groups) or '—'}")
    console.print(f"  session until · sessão:  {expires}")
