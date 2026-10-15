"""🇺🇸 Quickstart: credential, enrollment, first call.

`Diagnos()` finds the service account credential in `DIAGNOS_CREDENTIAL`
(or `DIAGNOS_CREDENTIALS_FILE`, or `~/.config/diagnos/credentials.json`) and
the vault in `DIAGNOS_VAULT_URL`. Entering the `with` block enrolls: the SDK
prints an approval link and a 6-digit code on stderr, a workspace admin
approves it in the web app, and the block continues. Then every resource
works — here, the first read.

🇧🇷 Quickstart: credencial, enrollment, primeira chamada.

`Diagnos()` acha a credencial da conta de serviço em `DIAGNOS_CREDENTIAL`
(ou `DIAGNOS_CREDENTIALS_FILE`, ou `~/.config/diagnos/credentials.json`) e o
cofre em `DIAGNOS_VAULT_URL`. Entrar no bloco `with` faz o enrollment: o SDK
imprime um link de aprovação e um código de 6 dígitos no stderr, um admin do
workspace aprova no app web, e o bloco continua. Daí todo recurso funciona —
aqui, a primeira leitura.
"""

from __future__ import annotations

import os
import sys

from diagnos import ConfigError, CredentialError, Diagnos, EnrollmentDeniedError, EnrollmentExpiredError

LEGACY_SUNSET = "2027-04-15"


def warn_if_legacy_token() -> None:
    """🇺🇸 Warns if only the legacy `DIAGNOS_API_TOKEN` is set. 🇧🇷 Avisa se só o `DIAGNOS_API_TOKEN` legado existe."""
    current = os.environ.get("DIAGNOS_CREDENTIAL") or os.environ.get("DIAGNOS_CREDENTIALS_FILE")
    if os.environ.get("DIAGNOS_API_TOKEN") and not current:
        print(
            f"warning: DIAGNOS_API_TOKEN is deprecated and stops working on {LEGACY_SUNSET}; create a service "
            "account credential and set DIAGNOS_CREDENTIAL (https://dev.diagnos.health/migrating) · "
            f"aviso: DIAGNOS_API_TOKEN está obsoleto e deixa de funcionar em {LEGACY_SUNSET}; crie uma "
            "credencial de conta de serviço e use DIAGNOS_CREDENTIAL (https://dev.diagnos.health/migrating)",
            file=sys.stderr,
        )


def main() -> int:
    """🇺🇸 Enrolls and reads the first page of patients; returns the exit code.

    🇧🇷 Faz o enrollment e lê a primeira página de pacientes; devolve o código de saída.
    """
    warn_if_legacy_token()
    try:
        # 🇺🇸 Enrolls on entry (prints the link + code) and closes the HTTP clients on exit.
        # 🇧🇷 Faz o enrollment na entrada (imprime o link + código) e fecha os clients HTTP na saída.
        with Diagnos() as vault:
            print(f"workspace: {vault.workspace_id}")
            print(f"credential: {vault.credential_kind} {vault.key_id}")
            print(f"groups: {', '.join(vault.security_groups) or '(none granted)'}")

            page = vault.patients.list(limit=5)
            print(f"first call ok: {len(page.items)} patient(s) on the first page")
    except ConfigError as error:
        print(f"configuration: {error}", file=sys.stderr)
        return 2
    except (EnrollmentDeniedError, EnrollmentExpiredError) as error:
        print(f"enrollment: {error.__class__.__name__}; run again for a new link and code", file=sys.stderr)
        return 3
    except CredentialError as error:
        print(f"credential refused ({error.__class__.__name__}): {error}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
