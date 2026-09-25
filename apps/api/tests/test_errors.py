"""🇺🇸 `errors.py`'s handlers that `test_patients.py`/`test_exams.py`'s happy paths never reach on their own.

`register_exception_handlers` wires eleven handlers; the "vault answered with
an envelope" ones (`ValidationError`/`AuthenticationError`/.../`VaultError`)
share one factory and get exercised plenty via `QuotaError` elsewhere. The
seven left over — `SessionExpiredError` (no `code`/`trace_id` to carry),
`CryptoError` (deliberately opaque), `ProtocolError` (the vault's fault, a
502), `GroupKeyUnavailable` (a permission gap, a 403), a route FastAPI
itself rejects
(`RequestValidationError`), a route that does not exist at all
(`HTTPException`'s plain-string fallback), and any `DiagnosError` this
module never named (`_unexpected_error_handler`) — are this file's whole
job.

🇧🇷 Os handlers de `errors.py` que os caminhos felizes de
`test_patients.py`/`test_exams.py` nunca alcançam sozinhos.

`register_exception_handlers` conecta onze handlers; os que "o cofre
respondeu com um envelope" (`ValidationError`/`AuthenticationError`/.../
`VaultError`) compartilham uma fábrica e já são exercitados bastante via
`QuotaError` em outro lugar. Os sete que sobram — `SessionExpiredError`
(sem `code`/`trace_id` para carregar), `CryptoError` (opaco de propósito),
`ProtocolError` (culpa do cofre, um 502), `GroupKeyUnavailable` (lacuna de
permissão, um 403), uma rota que o próprio FastAPI rejeita (`RequestValidationError`), uma rota
que não existe (o fallback de string pura do `HTTPException`), e qualquer
`DiagnosError` que este módulo nunca nomeou (`_unexpected_error_handler`) —
são o trabalho inteiro deste arquivo.
"""

from __future__ import annotations

import asyncio
import json

from diagnos import ConfigError, CryptoError, GroupKeyUnavailable, ProtocolError, SessionExpiredError
from fastapi import HTTPException
from fastapi.testclient import TestClient

from diagnos_api.errors import _http_exception_handler

from conftest import FakeDiagnos


def _create_body() -> dict[str, object]:
    """🇺🇸 A minimal valid `POST /v1/patients` body, reused across every handler test below.

    🇧🇷 Um corpo mínimo válido de `POST /v1/patients`, reusado em todo teste de handler abaixo.
    """
    return {"record": {"legal_name": "Jane Doe", "display_name": "Jane"}, "security_group": "sg1"}


def test_session_expired_is_401_without_code_or_trace_id(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `SessionExpiredError` is a plain `DiagnosError`, not a `VaultError` — its envelope has `code=None`.

    🇧🇷 `SessionExpiredError` é um `DiagnosError` puro, não um `VaultError` — o envelope tem `code=None`.
    """
    fake_vault.patients.raise_on_create = SessionExpiredError("session keys past expires_at")

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "session_expired",
        "message": "session keys past expires_at",
        "trace_id": None,
    }


def test_crypto_error_is_500_with_no_detail_leaked(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `CryptoError` never forwards its own message — "wrong key" and "tampered ciphertext" stay conflated.

    🇧🇷 `CryptoError` nunca encaminha a própria mensagem — "chave errada" e
    "ciphertext adulterado" continuam confundidos.
    """
    fake_vault.patients.raise_on_create = CryptoError("AEAD tag mismatch on DEK unwrap")

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "crypto_error"
    assert "AEAD" not in body["error"]["message"]
    assert body["error"]["message"] == "internal cryptographic error"


def test_protocol_error_is_502_naming_the_violation(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 A vault answer outside the protocol is the upstream's fault: 502, with the SDK's description.

    🇧🇷 Uma resposta do cofre fora do protocolo é culpa de quem está acima: 502, com a descrição do SDK.
    """
    fake_vault.patients.raise_on_create = ProtocolError("the vault signed 10 bytes for a 12-byte body")

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "protocol_error",
        "message": "the vault signed 10 bytes for a 12-byte body",
        "trace_id": None,
    }


def test_missing_group_key_is_403(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 No key for the data's group is a permission gap an admin can close — a 403, not a 500.

    🇧🇷 Sem chave para o grupo do dado é uma lacuna de permissão que um admin fecha — um 403, não um 500.
    """
    fake_vault.patients.raise_on_create = GroupKeyUnavailable("no key for 'sg1'")

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "group_key_unavailable"


def test_unmapped_diagnos_error_is_500_with_the_generic_envelope(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 A `DiagnosError` this module never named by class (`ConfigError`) still gets the uniform envelope.

    🇧🇷 Um `DiagnosError` que este módulo nunca nomeou por classe (`ConfigError`) ainda recebe o envelope uniforme.
    """
    fake_vault.patients.raise_on_create = ConfigError("unreachable in practice — the vault is unlocked by lifespan")

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"


def test_malformed_request_body_is_422_with_field_locations(client: TestClient) -> None:
    """🇺🇸 A body FastAPI itself rejects (`RequestValidationError`) is folded into the same envelope, not a raw 422.

    🇧🇷 Um corpo que o próprio FastAPI rejeita (`RequestValidationError`) é dobrado no mesmo envelope, não um 422 cru.
    """
    response = client.post("/v1/patients", json={"security_group": "sg1"})  # 🇺🇸 missing `record` 🇧🇷 sem `record`

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_request"
    assert "record" in body["error"]["message"]


def test_http_exception_handler_wraps_a_plain_string_detail_in_the_envelope() -> None:
    """🇺🇸 The handler's non-dict `detail` branch, called directly — nothing in this codebase raises one over HTTP.

    Every real `HTTPException` this API raises itself (`mtls.py`'s 401/403)
    already carries the envelope as `detail`; the fallback that wraps a
    plain string is otherwise only reachable through Starlette's own
    routing-layer `HTTPException` (404/405), which the tests below cover over
    HTTP. Calling it directly pins the branch on its own.

    🇧🇷 O ramo de `detail` não-dict do handler, chamado direto — nada neste
    código lança um assim por HTTP.

    Toda `HTTPException` que esta API de fato lança (`mtls.py`'s 401/403)
    já carrega o envelope como `detail`; o fallback que embrulha uma string
    pura só seria alcançável pela `HTTPException` da própria camada de
    roteamento do Starlette (404/405), que os testes abaixo cobrem por HTTP.
    Chamá-lo direto trava o ramo por conta própria.
    """
    exc = HTTPException(status_code=400, detail="a plain string, not our envelope dict")

    response = asyncio.run(_http_exception_handler(None, exc))  # type: ignore[arg-type]

    assert response.status_code == 400
    body = json.loads(bytes(response.body))
    assert body["error"] == {
        "code": "http_error",
        "message": "a plain string, not our envelope dict",
        "trace_id": None,
    }


def test_unknown_route_still_gets_the_uniform_error_envelope(client: TestClient) -> None:
    """🇺🇸 A route that does not exist answers in this API's own envelope, not Starlette's `{"detail": ...}`.

    Starlette's router raises its *base* `HTTPException` for 404/405, which
    is why the handler is registered for that class and not FastAPI's
    subclass.

    🇧🇷 Uma rota que não existe responde no envelope desta API, não no `{"detail": ...}` do Starlette.

    O roteador do Starlette lança a `HTTPException` *base* para 404/405, e é
    por isso que o handler é registrado para essa classe e não para a
    subclasse do FastAPI.
    """
    response = client.get("/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "http_error"
    assert body["error"]["trace_id"] is None


def test_wrong_method_on_an_existing_route_gets_the_uniform_error_envelope(client: TestClient) -> None:
    """🇺🇸 `405` from Starlette's router (a `DELETE` on a GET-only route) answers in this API's envelope too.

    🇧🇷 O `405` do roteador do Starlette (um `DELETE` numa rota só GET) também responde no envelope desta API.
    """
    response = client.delete("/v1/session")

    assert response.status_code == 405
    assert response.json()["error"] == {"code": "http_error", "message": "Method Not Allowed", "trace_id": None}
