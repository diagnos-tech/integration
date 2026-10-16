"""🇺🇸 End the session on purpose with `lock()`.

Leaving a `with` block only closes the HTTP clients: the session survives
(the vault shares it with every process using the same token, so a worker
that restarts picks it up again). `lock()` is the opposite, deliberate act:
it ends the session on the vault and wipes every key from this process. Use it when the work is really done —
a job that finishes, a shutdown hook, a suspected leak — in a `finally` so it
runs on failure too.

🇧🇷 Encerra a sessão de propósito com `lock()`.

Sair de um bloco `with` só fecha os clients HTTP: a sessão sobrevive (o
cofre a divide com todo processo que usa o mesmo token, então um worker que
reinicia a pega de novo). `lock()` é o ato oposto, deliberado: encerra a
sessão no cofre e apaga toda chave deste processo. Use quando o trabalho de fato acabou — um
job que termina, um gancho de desligamento, uma suspeita de vazamento — num
`finally`, para rodar também na falha.
"""

from __future__ import annotations

import sys

from diagnos import ConfigError, Diagnos, DiagnosError


def main() -> int:
    """🇺🇸 Works, then locks; returns the exit code. 🇧🇷 Trabalha, depois tranca; devolve o código de saída."""
    try:
        vault = Diagnos()
        try:
            vault.unlock()
            print(f"unlocked: {len(vault.security_groups)} group(s) granted")
            print(f"work done: {len(vault.patients.list(limit=5).items)} patient(s) on the first page")
        finally:
            # 🇺🇸 Best-effort on the vault, always wipes local keys; then free the sockets.
            # 🇧🇷 Best-effort no cofre, sempre apaga as chaves locais; depois libera os sockets.
            vault.lock()
            vault.close()
        print(f"locked: {len(vault.security_groups)} group(s) held after lock()")
    except ConfigError as error:
        print(f"configuration: {error}", file=sys.stderr)
        return 2
    except DiagnosError as error:
        print(f"{error.__class__.__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
