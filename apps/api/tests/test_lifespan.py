"""🇺🇸 The app's lifespan unlocks the vault on startup and closes it on shutdown — never `lock()`s it.

Shutdown closing is not conditioned on the requests served in between going
well: `_lifespan`'s `try/finally` (`app.py`) wraps the whole `yield`, so a
route answering a 404 or even a raw, unhandled Python exception still runs
`vault.close()` once the app's `with` block exits — this file's second test
pins that down for both cases, not just the happy path its first test
already covered.

🇧🇷 O lifespan do app desbloqueia o cofre na subida e o fecha no
desligamento — nunca o `lock()`.

O fechamento no desligamento não depende das requisições servidas no meio
terem ido bem: o `try/finally` de `_lifespan` (`app.py`) envolve o `yield`
inteiro, então uma rota respondendo um 404 ou até uma exceção Python crua e
não tratada ainda rodam `vault.close()` assim que o bloco `with` do app
termina — o segundo teste deste arquivo trava isso para os dois casos, não
só o caminho feliz que o primeiro teste já cobria.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diagnos_api.settings import ApiSettings

from conftest import FakeDiagnos, build_app


def test_startup_unlocks_and_shutdown_closes(fake_vault: FakeDiagnos, api_settings: ApiSettings) -> None:
    """🇺🇸 One `unlock()` by the time the app is serving; one `close()` once the `with` block exits.

    🇧🇷 Um `unlock()` até o app estar servindo; um `close()` assim que o bloco `with` termina.
    """
    app = build_app(fake_vault, api_settings)

    with TestClient(app) as client:
        assert fake_vault.unlock_calls == 1
        assert fake_vault.close_calls == 0
        response = client.get("/healthz")
        assert response.status_code == 200

    assert fake_vault.close_calls == 1
    # 🇺🇸 `Diagnos.__exit__`'s own reasoning (`apps/sdk/src/diagnos/client.py`):
    # a shutdown is "done talking to the vault now", not "revoke this
    # session forever" — `lock()` is a deliberate, separate call
    # (`POST /v1/session/lock`), never automatic.
    # 🇧🇷 O mesmo raciocínio de `Diagnos.__exit__` (`apps/sdk/src/diagnos/client.py`):
    # um desligamento é "terminei de falar com o cofre agora", não "revogue
    # esta sessão para sempre" — `lock()` é uma chamada deliberada e
    # separada (`POST /v1/session/lock`), nunca automática.
    assert fake_vault.lock_calls == 0


def test_shutdown_still_closes_after_a_request_that_answered_an_error(
    fake_vault: FakeDiagnos, api_settings: ApiSettings
) -> None:
    """🇺🇸 A request the API turned into a 404 does not stop `close()` from running once the app shuts down.

    🇧🇷 Uma requisição que a API transformou num 404 não impede `close()` de rodar quando o app desliga.
    """
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
    """🇺🇸 Even a raw exception no `errors.py` handler claims (not a `DiagnosError` at all) still lets `close()` run.

    `TestClient` re-raises an unhandled server exception at the call site
    instead of turning it into a response (`raise_server_exceptions=True`,
    its default) — this is deliberately the worst case: `_lifespan`'s
    `finally` is a property of the ASGI lifespan scope, entirely separate
    from any one request's outcome, so shutdown still has to close the
    vault's HTTP clients even after a request this API itself has no
    handler for at all.

    🇧🇷 Até uma exceção crua que nenhum handler de `errors.py` reivindica
    (nem sequer um `DiagnosError`) ainda deixa `close()` rodar.

    O `TestClient` relança uma exceção de servidor não tratada no próprio
    ponto da chamada em vez de virar uma resposta
    (`raise_server_exceptions=True`, o padrão dele) — isto é de propósito o
    pior caso: o `finally` de `_lifespan` é uma propriedade do escopo de
    lifespan do ASGI, inteiramente separada do resultado de qualquer
    requisição, então o desligamento ainda precisa fechar os clients HTTP do
    cofre mesmo depois de uma requisição para a qual esta API não tem handler
    nenhum.
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
