"""🇺🇸 `diagnos status` — what this token identifies, whether OpenBao is configured, whether secrets are locked in RAM.

🇧🇷 `diagnos status` — o que este token identifica, se o auto-unseal via
OpenBao está configurado, e se os segredos estão travados na RAM.
"""

from __future__ import annotations

import os

import typer
from diagnos import __version__ as sdk_version
from diagnos import memory_status

from diagnos_cli import context
from diagnos_cli.context import CliOptions
from diagnos_cli.render import get_console, get_err_console, print_json


def status(
    ctx: typer.Context,
    check: bool = typer.Option(
        False,
        "--check",
        help="Also unlock and list granted groups · Também desbloqueia e lista os grupos concedidos",
    ),
) -> None:
    """🇺🇸 Parses the token locally; only touches the network for `unlock()` when `--check` is given.

    `Diagnos.workspace_id`/`account_id` are read straight off the parsed
    token in `__init__` — building the client below never makes a request
    on its own. `name`/`key_id` are not on that list: `Diagnos` does not
    expose them (only `diagnos.transport.token.ServiceAccountToken`, which
    `cli` may not import — `CONVENTIONS.md` — does), so they show as
    "not exposed by the SDK" here instead of silently vanishing.

    🇧🇷 Interpreta o token localmente; só toca a rede para `unlock()` quando
    `--check` é passado.

    `Diagnos.workspace_id`/`account_id` são lidos direto do token já
    interpretado em `__init__` — construir o client abaixo nunca faz uma
    requisição por conta própria. `name`/`key_id` não estão nessa lista:
    `Diagnos` não os expõe (só `diagnos.transport.token.ServiceAccountToken`,
    que `cli` não pode importar — `CONVENTIONS.md` — os tem), então aparecem
    como "não exposto pelo SDK" aqui em vez de sumir em silêncio.
    """
    opts: CliOptions = ctx.obj
    console = get_console(opts)
    vault = context.build_client(opts)

    result: dict[str, object] = {
        "workspace_id": vault.workspace_id,
        "account_id": vault.account_id,
        "name": None,
        "key_id": None,
        "openbao_configured": bool(os.environ.get("OPENBAO_ADDR")),
        "sdk_version": sdk_version,
        "memory": _memory_summary(),
    }

    # 🇺🇸 Kept out of `result` (typed `dict[str, object]`) until printed, so
    # its element type (`list[str]`) survives for `", ".join(...)` below
    # instead of widening to `object` the moment it joins the dict.
    # 🇧🇷 Mantido fora de `result` (tipado `dict[str, object]`) até imprimir,
    # para o tipo do elemento (`list[str]`) sobreviver para `", ".join(...)`
    # abaixo em vez de alargar para `object` assim que entra no dict.
    security_groups: list[str] = []
    if check:
        err_console = get_err_console(opts)
        with context.enrollment_progress(err_console, quiet=opts.quiet) as on_prompt:
            vault = context.build_client(opts, on_prompt=on_prompt)
            vault.unlock()
        security_groups = vault.security_groups

    if opts.json_output:
        if check:
            result["security_groups"] = security_groups
        print_json(result)
        return
    console.print(f"  workspace_id: {result['workspace_id']}")
    console.print(f"  account_id:   {result['account_id']}")
    console.print("  name:         not exposed by the SDK · não exposto pelo SDK")
    console.print("  key_id:       not exposed by the SDK · não exposto pelo SDK")
    openbao_label = "configured · configurado" if result["openbao_configured"] else "not set · não definido"
    console.print(f"  openbao:      {openbao_label}")
    console.print(f"  sdk_version:  {result['sdk_version']}")
    console.print(f"  memory:       {_memory_label()}")
    if check:
        console.print(f"  groups · grupos: {', '.join(security_groups) or '—'}")


def _memory_summary() -> dict[str, object]:
    """🇺🇸 The enclave facts an operator acts on: policy, backend, and whether every secret is locked.

    🇧🇷 Os fatos do enclave em que um operador age: política, backend, e se todo segredo está travado.
    """
    status = memory_status()
    return {
        "backend": status.get("backend"),
        "lock_policy": status.get("lock_policy"),
        "live_secrets": status.get("live_secrets"),
        "unlocked_allocations": status.get("unlocked_allocations"),
        "guard_pages": status.get("guard_pages"),
        "wipe_on_fork": status.get("wipe_on_fork"),
    }


def _memory_label() -> str:
    """🇺🇸 One line: `locked` or how many allocations the kernel refused to lock.

    🇧🇷 Uma linha: `locked` ou quantas alocações o kernel se recusou a travar.
    """
    summary = _memory_summary()
    raw_unlocked = summary.get("unlocked_allocations")
    unlocked = raw_unlocked if isinstance(raw_unlocked, int) else 0
    if unlocked == 0:
        return f"locked in RAM · travada na RAM ({summary['backend']}, {summary['lock_policy']})"
    return (
        f"{unlocked} allocation(s) not locked · alocação(ões) sem trava "
        f"({summary['backend']}, {summary['lock_policy']}) — raise `ulimit -l` or grant CAP_IPC_LOCK"
    )
