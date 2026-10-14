"""`VaultTransport`: `close()`/context manager, the `put` shortcut, and an auth error that is not skew.

`test_http.py` drives `get`/`post` through every retry rule; this file rounds
out the surface it leaves untouched: the two clients actually get closed
(directly and via `with`), `put` builds the same kind of request `get`/`post`
do, and a `401` whose `code` is *not* `SignatureTimestampSkew` (or one on an
unsigned call) is never retried — it just raises, same as any other
`AuthenticationError`.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from diagnos.crypto.secure import SecretBox
from diagnos.errors import AuthenticationError
from diagnos.session.keyring import SessionKeys
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport
from diagnos.transport.token import ServiceAccountToken

_TOKEN = ServiceAccountToken(
    raw="apikey-test",
    key_id="key_1",
    account_id="acc_1",
    workspace_id="ws_1",
    name="svc@ws_1.diagnos.health",
)
_WIDGET_PATH = "/api/external/v1/workspaces/ws_1/widgets"


class _RecordingClient(httpx.Client):
    """An `httpx.Client` that remembers whether `close()` ran, on top of a `MockTransport`."""

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        """Starts open, wired to `handler`."""
        super().__init__(transport=httpx.MockTransport(handler), base_url="https://vault.example.test")
        self.closed_by_test = False

    def close(self) -> None:
        """Records the call, then closes for real."""
        self.closed_by_test = True
        super().close()


def _time_response(request: httpx.Request) -> httpx.Response:
    """The raw (unenveloped) shape `GET /time` answers with."""
    return httpx.Response(200, json={"result": 1_700_000_000_000})


def _envelope_success(result: object) -> httpx.Response:
    """A `success: true` envelope carrying `result`."""
    return httpx.Response(200, json={"success": True, "status": "success", "status_code": 200, "result": result})


def _envelope_error(code: str, *, status: int) -> httpx.Response:
    """A `success: false` envelope carrying one error `code`."""
    return httpx.Response(
        status,
        json={"success": False, "status": "fail", "status_code": status, "errors": [{"code": code}], "docs": "d"},
    )


def _settings() -> Settings:
    """Settings pointed at the mock base URL."""
    return Settings(api_token="apikey-test", vault_url="https://vault.example.test")  # noqa: S106


def _keys() -> SessionKeys:
    """Session keys valid far into the future."""
    return SessionKeys(
        session_id="sess_1",
        sign_key=SecretBox.random(32),
        enc_key=SecretBox.random(32),
        expires_at=9_999_999_999,
    )


def test_close_closes_both_the_api_and_the_storage_client() -> None:
    """`VaultTransport.close()` closes the signed client and the bare storage client."""
    api_client = _RecordingClient(lambda r: _time_response(r))
    storage_client = _RecordingClient(lambda r: httpx.Response(200))
    transport = VaultTransport(
        _settings(), _TOKEN, session_keys=lambda: None, client=api_client, storage_client=storage_client
    )

    transport.close()

    assert api_client.closed_by_test is True
    assert storage_client.closed_by_test is True


def test_context_manager_closes_both_clients_on_exit() -> None:
    """`with VaultTransport(...):` closes both clients on the way out, exception or not."""
    api_client = _RecordingClient(lambda r: _time_response(r))
    storage_client = _RecordingClient(lambda r: httpx.Response(200))

    with VaultTransport(
        _settings(), _TOKEN, session_keys=lambda: None, client=api_client, storage_client=storage_client
    ) as transport:
        assert isinstance(transport, VaultTransport)

    assert api_client.closed_by_test is True
    assert storage_client.closed_by_test is True


def test_put_sends_a_put_request_and_unwraps_the_result() -> None:
    """`put()` is the same shape as `get()`/`post()`, just with `PUT`."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return _time_response(request)
        seen["method"] = request.method
        return _envelope_success({"updated": True})

    keys = _keys()
    transport = VaultTransport(
        _settings(),
        _TOKEN,
        session_keys=lambda: keys,
        client=_RecordingClient(handler),
        storage_client=_RecordingClient(lambda r: httpx.Response(200)),
    )

    result = transport.put(_WIDGET_PATH, json={"a": 1})

    assert result == {"updated": True}
    assert seen["method"] == "PUT"


def test_an_authentication_error_that_is_not_skew_is_never_retried() -> None:
    """A `401` with a code other than `SignatureTimestampSkew` raises on the first attempt."""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return _time_response(request)
        attempts["n"] += 1
        return _envelope_error("InvalidSignature", status=401)

    keys = _keys()
    transport = VaultTransport(
        _settings(),
        _TOKEN,
        session_keys=lambda: keys,
        client=_RecordingClient(handler),
        storage_client=_RecordingClient(lambda r: httpx.Response(200)),
    )

    with pytest.raises(AuthenticationError) as excinfo:
        transport.get(_WIDGET_PATH)

    assert excinfo.value.code == "InvalidSignature"
    assert attempts["n"] == 1  # no retry attempted


def test_a_signature_timestamp_skew_on_an_unsigned_call_is_never_retried() -> None:
    """`SignatureTimestampSkew` only ever makes sense on a signed call; unsigned, it just raises."""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return _envelope_error("SignatureTimestampSkew", status=401)

    transport = VaultTransport(
        _settings(),
        _TOKEN,
        session_keys=lambda: (_ for _ in ()).throw(AssertionError("signed=False must never consult session_keys")),
        client=_RecordingClient(handler),
        storage_client=_RecordingClient(lambda r: httpx.Response(200)),
    )

    with pytest.raises(AuthenticationError) as excinfo:
        transport.get(_WIDGET_PATH, signed=False)

    assert excinfo.value.code == "SignatureTimestampSkew"
    assert attempts["n"] == 1
