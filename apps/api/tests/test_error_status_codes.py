"""🇺🇸 Every `VaultError` subclass `errors.py` maps to its own status code, plus the base class's 502 fallback.

`test_errors.py` already exercises `_vault_error_handler`'s factory through
`QuotaError`/`ConflictError`/`NotFoundError` (`test_patients.py`) and its own
seven special cases; this file's whole job is the five status codes that
share that factory but had no direct test of their own —
`ValidationError` (400), `AuthenticationError` (401, distinct from
`SessionExpiredError`'s own 401), `DiagnosPermissionError` (403, distinct from
`GroupKeyUnavailable`'s own 403), `RateLimitError` (429), and the base
`VaultError` itself (502) for a code none of its subclasses claim. Each of
these is a status code a real integrator's retry/backoff logic branches on
(`README.md`'s error table), so a silent regression in
`register_exception_handlers` on any one of them is worth catching by name,
not just incidentally through another class that happens to share a helper.

🇧🇷 Toda subclasse de `VaultError` que `errors.py` mapeia para o próprio
código de status, mais o fallback 502 da classe base.

`test_errors.py` já exercita a fábrica `_vault_error_handler` via
`QuotaError`/`ConflictError`/`NotFoundError` (`test_patients.py`) e os
próprios sete casos especiais; o trabalho inteiro deste arquivo são os cinco
códigos de status que compartilham essa fábrica mas não tinham teste direto
— `ValidationError` (400), `AuthenticationError` (401, distinto do 401 do
próprio `SessionExpiredError`), `DiagnosPermissionError` (403, distinto do
403 do próprio `GroupKeyUnavailable`), `RateLimitError` (429), e a própria
`VaultError` base (502) para um código que nenhuma subclasse reivindica. Cada
um destes é um código de status em que a lógica de retry/backoff de um
integrador de verdade decide o que fazer (a tabela de erro do `README.md`),
então uma regressão silenciosa em `register_exception_handlers` em qualquer
um deles vale a pena pegar pelo nome, não só incidentalmente por outra classe
que compartilha um helper.
"""

from __future__ import annotations

from diagnos import AuthenticationError, DiagnosPermissionError, RateLimitError, ValidationError, VaultError
from fastapi.testclient import TestClient

from conftest import FakeDiagnos


def _create_body() -> dict[str, object]:
    """🇺🇸 A minimal valid `POST /v1/patients` body, reused across every status-code test below.

    🇧🇷 Um corpo mínimo válido de `POST /v1/patients`, reusado em todo teste de código de status abaixo.
    """
    return {"record": {"legal_name": "Jane Doe", "display_name": "Jane"}, "security_group": "sg1"}


def test_validation_error_is_400_with_the_vaults_own_code_and_trace_id(
    client: TestClient, fake_vault: FakeDiagnos
) -> None:
    """🇺🇸 `ValidationError` — "the request itself is wrong" — answers 400, carrying the vault's code/trace_id as-is.

    🇧🇷 `ValidationError` — "a requisição está errada" — responde 400, carregando o code/trace_id do cofre como estão.
    """
    fake_vault.patients.raise_on_create = ValidationError(
        code="MissingField", message="`record.legal_name` is required", status=400, trace_id="trace-validation"
    )

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "MissingField",
        "message": "`record.legal_name` is required",
        "trace_id": "trace-validation",
    }


def test_authentication_error_is_401_distinct_from_session_expired(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `AuthenticationError` is a `VaultError` with its own code — unlike `SessionExpiredError`'s bare 401.

    Both map to 401 (`README.md`'s error table), but this one carries the
    vault's own `code`/`trace_id` through unchanged, exactly like every other
    `VaultError` subclass — the two 401s are not the same handler.

    🇧🇷 `AuthenticationError` é uma `VaultError` com código próprio —
    diferente do 401 nu de `SessionExpiredError`.

    Os dois mapeiam para 401 (tabela de erro do `README.md`), mas este
    carrega o `code`/`trace_id` do cofre sem mudar, igual a toda outra
    subclasse de `VaultError` — os dois 401 não são o mesmo handler.
    """
    fake_vault.patients.raise_on_create = AuthenticationError(
        code="TokenRejected", message="signature does not match", status=401, trace_id="trace-auth"
    )

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "TokenRejected",
        "message": "signature does not match",
        "trace_id": "trace-auth",
    }


def test_permission_error_is_403_distinct_from_group_key_unavailable(
    client: TestClient, fake_vault: FakeDiagnos
) -> None:
    """🇺🇸 `DiagnosPermissionError` — "not allowed here" — is a different 403 than `GroupKeyUnavailable`'s.

    🇧🇷 `DiagnosPermissionError` — "não pode fazer isto aqui" — é um 403 diferente do de `GroupKeyUnavailable`.
    """
    fake_vault.patients.raise_on_create = DiagnosPermissionError(
        code="ServiceAccountForbidden",
        message="this account may not create patients",
        status=403,
        trace_id="trace-perm",
    )

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "ServiceAccountForbidden",
        "message": "this account may not create patients",
        "trace_id": "trace-perm",
    }


def test_rate_limit_error_is_429_with_code_and_trace_id(client: TestClient, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 `RateLimitError` — "the SDK already retried with backoff" — still reaches the caller as 429, not swallowed.

    🇧🇷 `RateLimitError` — "o SDK já tentou de novo com backoff" — ainda chega a quem chama como 429, não é engolido.
    """
    fake_vault.patients.raise_on_create = RateLimitError(
        code="TooManyRequests", message="slow down", status=429, trace_id="trace-rate"
    )

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 429
    assert response.json()["error"] == {"code": "TooManyRequests", "message": "slow down", "trace_id": "trace-rate"}


def test_unmapped_vault_error_is_502_even_when_its_own_status_field_says_otherwise(
    client: TestClient, fake_vault: FakeDiagnos
) -> None:
    """🇺🇸 The base `VaultError` handler always answers 502 — `exc.status` is never consulted, only the class is.

    `register_exception_handlers` wires a fixed status code per *class*, not
    per instance: `VaultError(..., status=599)` still answers 502, because
    `_vault_error_handler`'s closure captures the status code at
    registration time and never reads `exc.status` at all. A future edit
    that tried to "just forward `exc.status`" would silently let an upstream
    vault dictate this API's own status codes — this test pins the current,
    safer behavior down by name.

    🇧🇷 O handler da `VaultError` base sempre responde 502 —
    `exc.status` nunca é consultado, só a classe importa.

    `register_exception_handlers` conecta um código de status fixo por
    *classe*, não por instância: `VaultError(..., status=599)` ainda
    responde 502, porque o closure de `_vault_error_handler` captura o
    código de status no momento do registro e nunca lê `exc.status`. Uma
    edição futura que tentasse "só repassar `exc.status`" deixaria em
    silêncio um cofre a montante ditar os próprios códigos de status desta
    API — este teste trava o comportamento atual, mais seguro, pelo nome.
    """
    fake_vault.patients.raise_on_create = VaultError(
        code="SomeFutureCode", message="a code this API has no subclass for", status=599, trace_id="trace-vault"
    )

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "SomeFutureCode",
        "message": "a code this API has no subclass for",
        "trace_id": "trace-vault",
    }
