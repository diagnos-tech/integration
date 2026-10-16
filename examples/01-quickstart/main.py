"""🇺🇸 Quickstart: the token, a session, the first call — no approval step.

`Diagnos()` finds the service account token in `DIAGNOS_TOKEN` (CI and
containers) or where `diagnos login` kept it (the system keyring, or
OpenBao), and the vault in `DIAGNOS_VAULT_URL`. Entering the `with` block
opens a session with one signed request — the vault checks both the
classic (Ed25519) and the post-quantum (ML-DSA-65) signature — and every
resource works. Here, the first read.

🇧🇷 Quickstart: o token, uma sessão, a primeira chamada — sem etapa de aprovação.

`Diagnos()` acha o token da conta de serviço em `DIAGNOS_TOKEN` (CI e
containers) ou onde o `diagnos login` o guardou (o chaveiro do sistema, ou o
OpenBao), e o cofre em `DIAGNOS_VAULT_URL`. Entrar no bloco `with` abre uma
sessão com uma requisição assinada — o cofre confere a assinatura clássica
(Ed25519) e a pós-quântica (ML-DSA-65) — e todo recurso funciona. Aqui, a
primeira leitura.
"""

from __future__ import annotations

import sys

from diagnos import ConfigError, CredentialError, Diagnos


def main() -> int:
    """🇺🇸 Opens a session and reads the first page of patients; returns the exit code.

    🇧🇷 Abre uma sessão e lê a primeira página de pacientes; devolve o código de saída.
    """
    try:
        # 🇺🇸 Opens the session on entry and closes the HTTP clients on exit.
        # 🇧🇷 Abre a sessão na entrada e fecha os clients HTTP na saída.
        with Diagnos() as vault:
            print(f"workspace: {vault.workspace_id}")
            print(f"token: {vault.identity} (from {vault.token_source})")
            print(f"groups: {', '.join(vault.security_groups) or '(none in scope)'}")

            page = vault.patients.list(limit=5)
            print(f"first call ok: {len(page.items)} patient(s) on the first page")
    except ConfigError as error:
        print(f"configuration: {error}", file=sys.stderr)
        return 2
    except CredentialError as error:
        print(f"token refused ({error.__class__.__name__}): {error}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
