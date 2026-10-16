"""🇺🇸 `/v1/session` — introspecting and ending this process's one SDK session.

🇧🇷 `/v1/session` — introspecção e encerramento da única sessão de SDK deste processo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from diagnos import Diagnos
from diagnos.api.deps import get_vault
from diagnos.api.errors import MTLS_RESPONSES
from diagnos.api.mtls import ClientIdentity, require_client_certificate
from diagnos.api.schemas import ClientIdentityView, SessionInfo

router = APIRouter(prefix="/v1/session", tags=["session"], responses=MTLS_RESPONSES)


@router.get(
    "",
    response_model=SessionInfo,
    summary="🇺🇸 Describe this session 🇧🇷 Descreve esta sessão",
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
    summary="🇺🇸 Lock this session 🇧🇷 Trava esta sessão",
    description="🇺🇸 Ends the SDK session (best-effort server-side, always locally) and wipes its key "
    "material. It does not open a new one: with a service account token the next data route does, with one "
    "signed request; with the legacy `apikey-` token the next data route enrolls again and waits for an "
    "approval. "
    "🇧🇷 Encerra a sessão do SDK (best-effort do lado do servidor, sempre localmente) e apaga o "
    "material de chave dela. Não abre outra: com um token de conta de serviço a próxima rota de dados abre, "
    "com uma requisição assinada; com o token legado `apikey-` a próxima rota de dados refaz o enrollment e "
    "espera uma aprovação.",
)
def lock_session(
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> dict[str, str]:
    """🇺🇸 Delegates to `Diagnos.lock`. 🇧🇷 Delega para `Diagnos.lock`."""
    vault.lock()
    return {"status": "locked"}
