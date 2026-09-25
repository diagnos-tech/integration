"""🇺🇸 The app's lifespan unlocks the vault on startup and closes it on shutdown — never `lock()`s it.

🇧🇷 O lifespan do app desbloqueia o cofre na subida e o fecha no desligamento — nunca o `lock()`.
"""

from __future__ import annotations

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
