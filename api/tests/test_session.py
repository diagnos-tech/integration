"""🇺🇸 `/v1/session`: describes this process's identity and the caller's mTLS identity, and can lock it.

🇧🇷 `/v1/session`: descreve a identidade deste processo e a identidade mTLS
de quem chama, e pode travá-la.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import TRUSTED_IDENTITY, FakeDiagnos


def test_get_session_reports_workspace_and_caller_identity(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `GET /v1/session` mixes `Diagnos`'s own identity with the verified mTLS `ClientIdentity`.

    🇧🇷 `GET /v1/session` mistura a identidade da própria `Diagnos` com a `ClientIdentity` mTLS verificada.
    """
    response = client.get("/v1/session")

    assert response.status_code == 200
    body = response.json()
    assert body["workspace_id"] == fake_vault.workspace_id
    assert body["account_id"] == fake_vault.account_id
    assert body["security_groups"] == fake_vault.security_groups
    assert body["client"] == {"common_name": TRUSTED_IDENTITY.common_name, "serial": TRUSTED_IDENTITY.serial}


def test_lock_session_calls_diagnos_lock_and_returns_202(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `POST /v1/session/lock` delegates to `Diagnos.lock` and answers `202` with `{"status": "locked"}`.

    🇧🇷 `POST /v1/session/lock` delega para `Diagnos.lock` e responde `202` com `{"status": "locked"}`.
    """
    response = client.post("/v1/session/lock")

    assert response.status_code == 202
    assert response.json() == {"status": "locked"}
    assert fake_vault.lock_calls == 1
