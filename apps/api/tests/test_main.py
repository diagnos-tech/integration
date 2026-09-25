"""🇺🇸 `main.run()`: the console-script wiring — settings load, `create_app`, and the `uvicorn.run` call itself.

No test here starts a real server: `uvicorn.run` blocks forever serving
requests, so every test replaces it with a stand-in that just records its
`kwargs`. `create_app` is replaced too in the "happy path" test, because
building a real one means constructing a real `Diagnos()` off
`DIAGNOS_API_TOKEN` — a concern `apps/api/tests` leaves entirely to `conftest.py`'s
fake, never to a real SDK token.

🇧🇷 `main.run()`: a fiação do console-script — carregar configuração,
`create_app`, e a própria chamada a `uvicorn.run`.

Nenhum teste aqui sobe um servidor de verdade: `uvicorn.run` bloqueia para
sempre servindo requisições, então todo teste o substitui por um objeto que
só grava os `kwargs`. `create_app` também é substituído no teste de
"caminho feliz", porque construir um de verdade significa construir uma
`Diagnos()` de verdade a partir de `DIAGNOS_API_TOKEN` — uma preocupação que
`apps/api/tests` deixa inteira para o fake de `conftest.py`, nunca para um token
de SDK de verdade.
"""

from __future__ import annotations

import logging
import ssl
from collections.abc import Iterator
from typing import Any

import pytest
from diagnos import ConfigError

from diagnos_api import main as main_module
from diagnos_api.mtls import ClientCertH11Protocol

_TLS_ENV = {
    "DIAGNOS_API_MTLS_CA_FILE": "/ca.pem",
    "DIAGNOS_API_TLS_CERT_FILE": "/tls.pem",
    "DIAGNOS_API_TLS_KEY_FILE": "/tls-key.pem",
}


@pytest.fixture(autouse=True)
def _clean_api_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 Every test starts with none of the `DIAGNOS_API_*` variables set — each one opts in explicitly.

    🇧🇷 Todo teste começa sem nenhuma variável `DIAGNOS_API_*` setada — cada um opta por elas de forma explícita.
    """
    for name in (
        "DIAGNOS_API_MTLS_CA_FILE",
        "DIAGNOS_API_TLS_CERT_FILE",
        "DIAGNOS_API_TLS_KEY_FILE",
        "DIAGNOS_API_HOST",
        "DIAGNOS_API_PORT",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _restore_logger_state() -> Iterator[None]:
    """🇺🇸 `run()` calls the real `configure_logging()` — undo its process-global handler change afterwards.

    🇧🇷 `run()` chama o `configure_logging()` de verdade — desfaz a mudança de handler global do processo depois.
    """
    snapshots = {
        name: (list(logging.getLogger(name).handlers), logging.getLogger(name).level, logging.getLogger(name).propagate)
        for name in ("diagnos_api", "diagnos")
    }
    yield
    for name, (handlers, level, propagate) in snapshots.items():
        logger = logging.getLogger(name)
        logger.handlers = handlers
        logger.level = level
        logger.propagate = propagate


def test_run_exits_2_when_api_settings_are_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 No mTLS CA/cert/key at all: `ApiSettings.from_env()` raises before `create_app` is ever called.

    🇧🇷 Nenhuma CA/cert/key de mTLS: `ApiSettings.from_env()` lança antes de `create_app` sequer ser chamada.
    """
    with pytest.raises(SystemExit) as exc_info:
        main_module.run()

    assert exc_info.value.code == 2
    assert "DIAGNOS_API_MTLS_CA_FILE" in capsys.readouterr().err


def test_run_exits_2_when_create_app_raises_config_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 Valid `ApiSettings` but no `DIAGNOS_API_TOKEN`: `create_app`'s own `Diagnos()` raises `ConfigError`.

    🇧🇷 `ApiSettings` válida mas sem `DIAGNOS_API_TOKEN`: a própria `Diagnos()` de `create_app` lança `ConfigError`.
    """
    for name, value in _TLS_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(main_module, "create_app", lambda settings: (_ for _ in ()).throw(ConfigError("no token")))

    with pytest.raises(SystemExit) as exc_info:
        main_module.run()

    assert exc_info.value.code == 2
    assert "no token" in capsys.readouterr().err


def test_run_serves_https_with_mandatory_client_certificates(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 On success, `uvicorn.run` is called once, with the app, the mTLS `ssl_*` kwargs, and the patched protocol.

    🇧🇷 No sucesso, `uvicorn.run` é chamado uma vez, com o app, os `kwargs` `ssl_*` de mTLS, e o protocolo remendado.
    """
    for name, value in _TLS_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("DIAGNOS_API_HOST", "127.0.0.1")
    monkeypatch.setenv("DIAGNOS_API_PORT", "9443")

    sentinel_app = object()
    monkeypatch.setattr(main_module, "create_app", lambda settings: sentinel_app)
    recorded: dict[str, Any] = {}

    def fake_run(app: object, **kwargs: Any) -> None:
        recorded["app"] = app
        recorded.update(kwargs)

    monkeypatch.setattr(main_module.uvicorn, "run", fake_run)

    main_module.run()

    assert recorded["app"] is sentinel_app
    assert recorded["host"] == "127.0.0.1"
    assert recorded["port"] == 9443
    assert recorded["http"] is ClientCertH11Protocol
    assert recorded["log_config"] is None
    assert recorded["ssl_certfile"] == "/tls.pem"
    assert recorded["ssl_keyfile"] == "/tls-key.pem"
    assert recorded["ssl_ca_certs"] == "/ca.pem"
    assert recorded["ssl_cert_reqs"] == ssl.CERT_REQUIRED
