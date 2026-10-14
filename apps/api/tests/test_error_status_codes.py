"""Every `VaultError` subclass `errors.py` maps to its own status code, plus the base class's 502 fallback.

`test_errors.py` already exercises the factory behind `_vault_error_handler` through `QuotaError`, `ConflictError`
and `NotFoundError` (`test_patients.py`), plus its own seven special cases. This file covers the five status codes that
share that factory but have no direct test of their own:

- `ValidationError` (400).
- `AuthenticationError` (401, distinct from the 401 of `SessionExpiredError`).
- `DiagnosPermissionError` (403, distinct from the 403 of `GroupKeyUnavailable`).
- `RateLimitError` (429).
- The base `VaultError` itself (502), for a code that none of its subclasses claim.

A real integrator's retry and backoff logic branches on each of these status codes (the error table in `README.md`),
so a silent regression in `register_exception_handlers` on any one of them is worth catching by name, not just
incidentally through another class that happens to share a helper.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from diagnos import AuthenticationError, DiagnosPermissionError, RateLimitError, ValidationError, VaultError

from conftest import FakeDiagnos


def _create_body() -> dict[str, object]:
    """A minimal valid `POST /v1/patients` body, reused across every status-code test below."""
    return {"record": {"legal_name": "Jane Doe", "display_name": "Jane"}, "security_group": "sg1"}


def test_validation_error_is_400_with_the_vaults_own_code_and_trace_id(
    client: TestClient, fake_vault: FakeDiagnos
) -> None:
    """`ValidationError` ("the request itself is wrong") answers 400, carrying the vault's code and trace_id as-is."""
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
    """`AuthenticationError` is a `VaultError` with its own code, unlike the bare 401 of `SessionExpiredError`.

    Both map to 401 (the error table in `README.md`), but this one carries the vault's own `code` and `trace_id`
    through unchanged, exactly like every other `VaultError` subclass. The two 401s are not the same handler.
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
    """`DiagnosPermissionError` ("not allowed here") is a different 403 than the one for `GroupKeyUnavailable`."""
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
    """`RateLimitError` ("the SDK already retried with backoff") still reaches the caller as a 429, not swallowed."""
    fake_vault.patients.raise_on_create = RateLimitError(
        code="TooManyRequests", message="slow down", status=429, trace_id="trace-rate"
    )

    response = client.post("/v1/patients", json=_create_body())

    assert response.status_code == 429
    assert response.json()["error"] == {"code": "TooManyRequests", "message": "slow down", "trace_id": "trace-rate"}


def test_unmapped_vault_error_is_502_even_when_its_own_status_field_says_otherwise(
    client: TestClient, fake_vault: FakeDiagnos
) -> None:
    """The base `VaultError` handler always answers 502; `exc.status` is never consulted, only the class is.

    `register_exception_handlers` wires a fixed status code per *class*, not per instance: `VaultError(..., status=599)`
    still answers 502, because the closure in `_vault_error_handler` captures the status code at registration time and
    never reads `exc.status`. A future edit that tried to "just forward `exc.status`" would silently let an upstream
    vault dictate this API's own status codes, so this test pins the current, safer behavior by name.
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
