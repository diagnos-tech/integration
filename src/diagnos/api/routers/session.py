"""`/v1/session`: introspecting and ending this process's one SDK session."""

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
    summary="Describe this session",
    description="This process's workspace/account and unlocked security groups, plus the caller's own mTLS identity.",
)
def get_session(
    vault: Diagnos = Depends(get_vault),
    identity: ClientIdentity = Depends(require_client_certificate),
) -> SessionInfo:
    """Reads `Diagnos`'s own identity properties; never touches the network."""
    return SessionInfo(
        workspace_id=vault.workspace_id,
        account_id=vault.account_id,
        security_groups=vault.security_groups,
        client=ClientIdentityView(common_name=identity.common_name, serial=identity.serial),
    )


@router.post(
    "/lock",
    status_code=202,
    summary="Lock this session",
    description="Ends the SDK session (best-effort server-side, always locally) and wipes its key material. Every "
    "route after this one fails until the process is restarted and re-enrolls (or restores via OpenBao); this does "
    "not restart the session itself.",
)
def lock_session(
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> dict[str, str]:
    """Delegates to `Diagnos.lock`."""
    vault.lock()
    return {"status": "locked"}
