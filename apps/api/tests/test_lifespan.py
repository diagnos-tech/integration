"""The app's lifespan unlocks the vault on startup and closes it on shutdown, never calling `lock()`.

Closing on shutdown does not depend on the requests served in between going well. The `try/finally` of `_lifespan`
(`app.py`) wraps the whole `yield`, so a route answering a 404, or even a raw unhandled Python exception, still runs
`vault.close()` once the app's `with` block exits. The tests after the first pin that down for both cases, not just
the happy path.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diagnos.api.settings import ApiSettings

from conftest import FakeDiagnos, build_app


def test_startup_unlocks_and_shutdown_closes(fake_vault: FakeDiagnos, api_settings: ApiSettings) -> None:
    """One `unlock()` by the time the app is serving; one `close()` once the `with` block exits."""
    app = build_app(fake_vault, api_settings)

    with TestClient(app) as client:
        assert fake_vault.unlock_calls == 1
        assert fake_vault.close_calls == 0
        response = client.get("/healthz")
        assert response.status_code == 200

    assert fake_vault.close_calls == 1
    # Same reasoning as `Diagnos.__exit__` (`apps/sdk/src/diagnos/client.py`): a shutdown means "done talking to the
    # vault now", not "revoke this session forever". `lock()` is a deliberate, separate call
    # (`POST /v1/session/lock`) and is never automatic.
    assert fake_vault.lock_calls == 0


def test_shutdown_still_closes_after_a_request_that_answered_an_error(
    fake_vault: FakeDiagnos, api_settings: ApiSettings
) -> None:
    """A request the API turned into a 404 does not stop `close()` from running once the app shuts down."""
    app = build_app(fake_vault, api_settings)

    with TestClient(app) as client:
        response = client.get("/v1/patients/does-not-exist")
        assert response.status_code == 404
        assert fake_vault.close_calls == 0

    assert fake_vault.close_calls == 1
    assert fake_vault.lock_calls == 0


def test_shutdown_still_closes_after_a_request_that_raised_unhandled(
    fake_vault: FakeDiagnos, api_settings: ApiSettings
) -> None:
    """Even a raw exception that no `errors.py` handler claims (not a `DiagnosError`) still lets `close()` run.

    `TestClient` re-raises an unhandled server exception at the call site instead of turning it into a response
    (`raise_server_exceptions=True`, its default). That is deliberately the worst case: the `finally` of `_lifespan` is
    a property of the ASGI lifespan scope, entirely separate from any one request's outcome, so shutdown still has to
    close the vault's HTTP clients even after a request this API has no handler for at all.
    """
    fake_vault.patients.raise_on_create = ValueError("not a DiagnosError at all")
    app = build_app(fake_vault, api_settings)
    body = {"record": {"legal_name": "Jane Doe", "display_name": "Jane"}, "security_group": "sg1"}

    with TestClient(app) as client:
        with pytest.raises(ValueError, match="not a DiagnosError"):
            client.post("/v1/patients", json=body)
        assert fake_vault.close_calls == 0

    assert fake_vault.close_calls == 1
    assert fake_vault.lock_calls == 0
