"""🇺🇸 `/v1/session` — introspecting and ending this process's one SDK session.

🇧🇷 `/v1/session` — introspecção e encerramento da única sessão de SDK deste processo.
"""

from __future__ import annotations

from diagnos import Diagnos
from fastapi import APIRouter, Depends

from diagnos_api.deps import get_vault
from diagnos_api.mtls import ClientIdentity, require_client_certificate
from diagnos_api.schemas import ClientIdentityView, SessionInfo

router = APIRouter(prefix="/v1/session", tags=["session"])


@router.get(
    "",
    response_model=SessionInfo,
    summary="Describe this session · Descreve esta sessão",
    description="🇺🇸 This process's workspace/account and unlocked security groups, plus the caller's own "
    "mTLS identity. "
    "🇧🇷 O workspace/conta deste processo e os security groups desbloqueados, mais a identidade mTLS "
    "de quem chamou.",
)
def get_session(
    vault: Diagnos = Depends(get_vault),
    identity: ClientIdentity = Depends(require_client_certificate),
) -> SessionInfo:
    """🇺🇸 Reads `Diagnos`'s own identity properties; never touches the network.

    🇧🇷 Lê as próprias propriedades de identidade do `Diagnos`; nunca toca a rede.
    """
    return SessionInfo(
        workspace_id=vault.workspace_id,
        account_id=vault.account_id,
        security_groups=vault.security_groups,
        client=ClientIdentityView(common_name=identity.common_name, serial=identity.serial),
    )


@router.post(
    "/lock",
    status_code=202,
    summary="Lock this session · Trava esta sessão",
    description="🇺🇸 Ends the SDK session (best-effort server-side, always locally) and wipes its key "
    "material. Every route after this one fails until the process is restarted and re-enrolls (or "
    "restores via OpenBao) — this does not restart the session itself. "
    "🇧🇷 Encerra a sessão do SDK (best-effort do lado do servidor, sempre localmente) e apaga o "
    "material de chave dela. Toda rota depois desta falha até o processo reiniciar e refazer o "
    "enrollment (ou restaurar via OpenBao) — isto não reinicia a sessão sozinho.",
)
def lock_session(
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> dict[str, str]:
    """🇺🇸 Delegates to `Diagnos.lock`. 🇧🇷 Delega para `Diagnos.lock`."""
    vault.lock()
    return {"status": "locked"}
