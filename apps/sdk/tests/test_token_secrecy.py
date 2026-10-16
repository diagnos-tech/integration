"""🇺🇸 Nothing of the token in any log line, `repr` or rendered traceback — over a whole session, failures included.

A real `Diagnos` runs against a fake vault: the session opens, a call is
refused (`CredentialKeyRevoked`), the lock fails on the network. Every log
record at `DEBUG`, every rendered exception and every `repr` on the way is
searched for the token text, its seed (hex and base64url) and any window of
them.

🇧🇷 Nada do token em linha de log, `repr` ou traceback renderizado — numa sessão inteira, falhas incluídas.

Uma `Diagnos` de verdade roda contra um cofre falso: a sessão abre, uma
chamada é recusada (`CredentialKeyRevoked`), o lock falha na rede. Todo
registro de log em `DEBUG`, toda exceção renderizada e todo `repr` no caminho
são vasculhados atrás do texto do token, da semente (hex e base64url) e de
qualquer janela deles.
"""

from __future__ import annotations

import logging
import secrets
import traceback

import httpx
import pytest
from _token_vault import session_answer
from _tokens import mint

from diagnos import CredentialRevokedError, Diagnos, Settings
from diagnos.crypto.encoding import b64url_encode
from diagnos.transport.http import VaultTransport
from diagnos.transport.service_token import DiagnosToken

SEED = secrets.token_bytes(32)
TEXT = mint("wsSecret", seed=SEED)


def _secrets() -> list[str]:
    """🇺🇸 The token, its body, and the seed in two spellings. 🇧🇷 O token, o corpo dele, e a semente em duas grafias."""
    return [TEXT, TEXT[8:40], TEXT[40:72], SEED.hex(), b64url_encode(SEED)[:24]]


def _handler(request: httpx.Request) -> httpx.Response:
    """🇺🇸 `/time`, the session route, a revoked key elsewhere, and a lock that breaks. 🇧🇷 O cofre falso."""
    if request.url.path == "/time":
        return httpx.Response(200, json={"result": 1_760_000_000_000})
    if request.url.path.endswith("/session/lock"):
        raise httpx.ConnectError("down", request=request)
    if request.url.path.endswith("/session"):
        return httpx.Response(201, json={"success": True, "result": session_answer(DiagnosToken.parse(TEXT))})
    error = {"code": "CredentialKeyRevoked", "message": "revoked", "trace_id": "tr"}
    return httpx.Response(401, json={"success": False, "errors": [error]})


def test_a_whole_session_logs_and_raises_nothing_of_the_token(caplog: pytest.LogCaptureFixture) -> None:
    """🇺🇸 Open, a refused call, a failed lock: logs, tracebacks and `repr`s stay clean.

    🇧🇷 Abrir, uma chamada recusada, um lock que falha: logs, tracebacks e `repr`s ficam limpos.
    """
    caplog.set_level(logging.DEBUG)
    settings = Settings.from_env({"DIAGNOS_TOKEN": TEXT, "DIAGNOS_VAULT_URL": "https://vault.test"})
    vault = Diagnos(settings=settings)
    vault._transport._client = httpx.Client(  # noqa: SLF001
        base_url="https://vault.test", transport=httpx.MockTransport(_handler)
    )
    vault.unlock()
    with pytest.raises(CredentialRevokedError) as caught:
        vault._transport.get("/api/external/v1/workspaces/wsSecret/patients")  # noqa: SLF001
    vault.lock()
    rendered = "".join(traceback.format_exception(caught.value))
    shown = "\n".join([caplog.text, rendered, repr(vault), repr(settings)])
    for secret in _secrets():
        assert secret not in shown, secret
    assert "Create a new token" in rendered
    assert any("session/lock failed" in record.getMessage() for record in caplog.records)
    assert isinstance(vault._transport, VaultTransport)  # noqa: SLF001
