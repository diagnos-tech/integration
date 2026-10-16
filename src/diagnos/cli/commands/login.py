"""🇺🇸 `diagnos login` — paste the token once; it is checked, proven against the vault, and kept somewhere safe.

The token is read with hidden input (pasting works), its CRC is checked
before any network call — a token cut short says so — then `whoami` proves
it: a session only opens when the vault verifies both the Ed25519 and the
ML-DSA-65 signature. Only then is it stored: in the system keyring when
there is one that encrypts at rest, else in OpenBao when `OPENBAO_ADDR` is
set, else nowhere, with the reason (`diagnos.save_token`). Never in a text
file. `DIAGNOS_TOKEN` still wins over what is stored, for CI and
containers.

🇧🇷 `diagnos login` — cole o token uma vez; ele é conferido, provado contra o cofre e guardado num lugar seguro.

O token é lido com entrada oculta (colar funciona), o CRC é conferido antes
de qualquer rede — um token cortado diz isso — e então o `whoami` o prova:
uma sessão só abre quando o cofre verifica as assinaturas Ed25519 e
ML-DSA-65. Só então ele é guardado: no chaveiro do sistema quando há um que
cifra em repouso, senão no OpenBao quando `OPENBAO_ADDR` está definida,
senão em lugar nenhum, com o motivo (`diagnos.save_token`). Nunca em arquivo
de texto. O `DIAGNOS_TOKEN` ainda vence o que está guardado, para CI e
containers.
"""

from __future__ import annotations

import contextlib
import dataclasses
import os
from typing import Literal

import typer

from diagnos import DiagnosToken, Settings, save_token
from diagnos.cli import context
from diagnos.cli.context import CliOptions
from diagnos.cli.render import get_console, get_err_console, print_json

StoreOption = Literal["auto", "keyring", "openbao"]


def _read_token() -> str:
    """🇺🇸 Hidden input on the terminal; a pipe works too (`… | diagnos login`).

    🇧🇷 Entrada oculta no terminal; um pipe também serve (`… | diagnos login`).
    """
    text: str = typer.prompt("Token (dgn_sk1_…)", hide_input=True, err=True)
    return text


def login(
    ctx: typer.Context,
    store: StoreOption = typer.Option(
        "auto",
        "--store",
        help=(
            "Where to keep the token: the system keyring, else OpenBao (auto) · Onde guardar o token: o chaveiro "
            "do sistema, senão o OpenBao (auto)"
        ),
    ),
) -> None:
    """🇺🇸 Reads the token, checks its CRC, proves it with `whoami`, stores it, and says where.

    🇧🇷 Lê o token, confere o CRC, prova com `whoami`, guarda e diz onde.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    text = _read_token()
    try:
        DiagnosToken.parse(text, source="diagnos login").wipe()
        # 🇺🇸 No auto-unseal: this session only proves the token, and the OpenBao token here may be a writer that
        # can store the diagnos token and nothing else (`token-writer-policy.hcl`).
        # 🇧🇷 Sem auto-unseal: esta sessão só prova o token, e o token do OpenBao aqui pode ser um de escrita que
        # só pode guardar o token do diagnos (`token-writer-policy.hcl`).
        vault = context.build_client(dataclasses.replace(opts, token=text), auto_unseal=False)
        who = vault.whoami()
        where = save_token(text, settings=Settings.without_token(context.environment(opts)), store=store)
    finally:
        # 🇺🇸 No frame keeps the pasted text once a command error is rendered. 🇧🇷 Nenhum quadro guarda o texto colado.
        del text
    # 🇺🇸 The session existed only to prove the token; end it on the vault too. 🇧🇷 A sessão só provou o token.
    with contextlib.suppress(Exception):
        vault.lock()
    vault.close()
    shadowing = [name for name in ("DIAGNOS_TOKEN", "DIAGNOS_API_TOKEN") if os.environ.get(name)]
    if opts.json_output:
        print_json({**dataclasses.asdict(who), "stored_in": where, "shadowed_by": shadowing})
        return
    console.print("[bold green]Logged in · Sessão iniciada[/bold green]")
    console.print(f"  identity · identidade: {who.identity}")
    console.print(f"  groups · grupos:       {', '.join(who.security_groups) or '—'}")
    console.print(f"  stored in · guardado:  {where}")
    if shadowing:
        get_err_console(opts).print(
            f"[yellow]{', '.join(shadowing)} is set in this shell and wins over the stored token; unset it to use it. "
            f"{', '.join(shadowing)} está definida neste shell e vence o token guardado; remova-a para usá-lo.[/yellow]"
        )
