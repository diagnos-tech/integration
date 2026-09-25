"""🇺🇸 `VaultTransport`: envelope unwrapping, every retry rule, and the seed/storage side channels.

Each test drives a real `httpx.Client` bound to an `httpx.MockTransport`
handler instead of mocking `VaultTransport`'s own methods — that way a bug in
how it builds headers, re-signs a retry, or reads `Retry-After` shows up the
same way it would against the real vault.

🇧🇷 `VaultTransport`: desembrulho de envelope, toda regra de retentativa, e os canais paralelos de seed/storage.

Cada teste roda um `httpx.Client` de verdade preso a um handler de
`httpx.MockTransport`, em vez de mockar os métodos do próprio
`VaultTransport` — assim um bug em como ele monta headers, reassina uma
retentativa ou lê `Retry-After` aparece do mesmo jeito que apareceria contra
o cofre de verdade.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable, Mapping

import httpx
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.secure import SecretBox
from diagnos.errors import QuotaError, RateLimitError, VaultError
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


def _fresh_session_keys() -> SessionKeys:
    """🇺🇸 A session that will not expire mid-test. 🇧🇷 Uma sessão que não expira no meio do teste."""
    return SessionKeys(
        session_id="sess_1",
        sign_key=SecretBox.from_bytes(bytearray(secrets.token_bytes(32))),
        enc_key=SecretBox.from_bytes(bytearray(secrets.token_bytes(32))),
        expires_at=9_999_999_999,
    )


def _time_response(request: httpx.Request) -> httpx.Response:
    """🇺🇸 The raw (unenveloped) shape `/time` answers with. 🇧🇷 A forma crua (sem envelope) com que `/time` responde."""
    body = json.loads(request.content or b"{}")
    return httpx.Response(200, json={"id": body.get("id"), "result": 1_700_000_000_000})


def _envelope_success(result: object, status: int = 200) -> httpx.Response:
    """🇺🇸 A `success: true` envelope carrying `result`. 🇧🇷 Um envelope `success: true` carregando `result`."""
    return httpx.Response(
        status,
        json={"success": True, "status": "success", "status_code": status, "result": result, "docs": "d"},
    )


def _envelope_error(
    code: str,
    *,
    status: int,
    message: str = "boom",
    trace_id: str | None = None,
    request_id: str | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> httpx.Response:
    """🇺🇸 A `success: false` envelope carrying one error `code`.

    🇧🇷 Um envelope `success: false` carregando um `code` de erro.
    """
    headers = dict(extra_headers or {})
    if request_id is not None:
        headers["X-Request-Id"] = request_id
    return httpx.Response(
        status,
        headers=headers,
        json={
            "success": False,
            "status": "error" if status >= 500 else "fail",
            "status_code": status,
            "errors": [{"code": code, "message": message, "trace_id": trace_id}],
            "docs": "d",
        },
    )


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    """🇺🇸 An `httpx.Client` wired to a `MockTransport` instead of a socket.

    🇧🇷 Um `httpx.Client` ligado a um `MockTransport` em vez de um socket.
    """
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://vault.example.test")


def _dummy_client() -> httpx.Client:
    """🇺🇸 A signed-side client that always succeeds, for storage-only tests.

    🇧🇷 Um client do lado assinado que sempre dá certo, para testes só de storage.
    """
    return _client(
        lambda request: httpx.Response(
            200,
            json={"success": True, "status": "success", "status_code": 200, "result": None, "docs": "d"},
        )
    )


def _make_transport(
    *,
    client: httpx.Client,
    storage_client: httpx.Client | None = None,
    session_keys: Callable[[], SessionKeys | None] | None = None,
    on_seed: Callable[[SecretBox], None] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> VaultTransport:
    """🇺🇸 A `VaultTransport` with sane defaults, overridable one at a time.

    🇧🇷 Um `VaultTransport` com padrões razoáveis, sobrescrevíveis um a um.
    """
    keys = _fresh_session_keys()
    settings = Settings(api_token="apikey-test", vault_url="https://vault.example.test")  # noqa: S106 — a fake token fixture, not a real secret
    return VaultTransport(
        settings,
        _TOKEN,
        session_keys=session_keys if session_keys is not None else (lambda: keys),
        on_seed=on_seed,
        client=client,
        storage_client=storage_client if storage_client is not None else _client(lambda r: httpx.Response(200)),
        sleep=sleep if sleep is not None else (lambda seconds: None),
    )


def test_success_unwraps_result_and_signs_the_request() -> None:
    """🇺🇸 A 2xx envelope unwraps to `result`, signed with all three headers.

    🇧🇷 Um envelope 2xx desembrulha para `result`, assinado com os três headers.
    """
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return _time_response(request)
        seen_headers.update(request.headers)
        return _envelope_success({"ok": True})

    transport = _make_transport(client=_client(handler))
    result = transport.get(_WIDGET_PATH)

    assert result == {"ok": True}
    assert seen_headers["authorization"] == "Bearer apikey-test"
    assert "x-signature-hmac" in seen_headers
    assert "x-signature-nonce" in seen_headers
    assert "x-signature-timestamp" in seen_headers


def test_quota_error_carries_code_trace_id_and_request_id() -> None:
    """🇺🇸 402 becomes `QuotaError` with `code`/`trace_id`/`request_id` intact.

    🇧🇷 402 vira `QuotaError` com `code`/`trace_id`/`request_id` intactos.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return _time_response(request)
        return _envelope_error("QuotaExceeded", status=402, message="no credit", trace_id="trace-1", request_id="req-1")

    transport = _make_transport(client=_client(handler))
    with pytest.raises(QuotaError) as excinfo:
        transport.post(_WIDGET_PATH, json={"a": 1})

    error = excinfo.value
    assert error.code == "QuotaExceeded"
    assert error.status == 402
    assert error.trace_id == "trace-1"
    assert error.request_id == "req-1"


def test_replay_detected_retries_once_with_a_different_nonce() -> None:
    """🇺🇸 `409 ReplayDetected` is retried exactly once, with a fresh nonce.

    🇧🇷 `409 ReplayDetected` é retentado exatamente uma vez, com nonce novo.
    """
    nonces: list[str] = []
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return _time_response(request)
        nonces.append(request.headers["X-Signature-Nonce"])
        attempts["n"] += 1
        if attempts["n"] == 1:
            return _envelope_error("ReplayDetected", status=409)
        return _envelope_success({"ok": True})

    transport = _make_transport(client=_client(handler))
    result = transport.post(_WIDGET_PATH, json={"a": 1})

    assert result == {"ok": True}
    assert attempts["n"] == 2
    assert len(nonces) == 2
    assert nonces[0] != nonces[1]


def test_replay_detected_a_second_time_is_not_retried_again() -> None:
    """🇺🇸 A second `ReplayDetected` in a row is not retried again; it raises.

    🇧🇷 Um segundo `ReplayDetected` seguido não é retentado de novo; ele explode.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return _time_response(request)
        return _envelope_error("ReplayDetected", status=409)

    transport = _make_transport(client=_client(handler))
    with pytest.raises(VaultError) as excinfo:
        transport.post(_WIDGET_PATH, json={"a": 1})
    assert excinfo.value.code == "ReplayDetected"


def test_signature_timestamp_skew_resyncs_the_clock_and_retries_once() -> None:
    """🇺🇸 `401 SignatureTimestampSkew` resyncs the clock and retries once.

    🇧🇷 `401 SignatureTimestampSkew` ressincroniza o relógio e retenta uma vez.
    """
    time_calls = {"n": 0}
    widget_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            time_calls["n"] += 1
            return _time_response(request)
        widget_calls["n"] += 1
        if widget_calls["n"] == 1:
            return _envelope_error("SignatureTimestampSkew", status=401)
        return _envelope_success({"ok": True})

    transport = _make_transport(client=_client(handler))
    result = transport.get(_WIDGET_PATH)

    assert result == {"ok": True}
    assert widget_calls["n"] == 2
    # 🇺🇸 One `sync()` before the first attempt (clock starts unsynced) plus one
    # resync triggered by the skew error — each `sync()` is 3 round trips
    # (`docs/PROTOCOL.md §2`), so two syncs is six `/time` calls.
    # 🇧🇷 Um `sync()` antes da primeira tentativa (relógio começa
    # dessincronizado) mais um resync disparado pelo erro de skew — cada
    # `sync()` são 3 idas e voltas (`docs/PROTOCOL.md §2`), então dois syncs
    # são seis chamadas a `/time`.
    assert time_calls["n"] == 6


def test_rate_limit_retries_up_to_three_times_honouring_retry_after() -> None:
    """🇺🇸 `429` retries up to three times, sleeping exactly what `Retry-After` says.

    🇧🇷 `429` retenta até três vezes, dormindo exatamente o que `Retry-After` diz.
    """
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return _time_response(request)
        attempts["n"] += 1
        return _envelope_error("RateLimitExceeded", status=429, extra_headers={"Retry-After": "0"})

    sleeps: list[float] = []
    transport = _make_transport(client=_client(handler), sleep=sleeps.append)

    with pytest.raises(RateLimitError):
        transport.get(_WIDGET_PATH)

    assert attempts["n"] == 4  # 🇺🇸/🇧🇷 initial + 3 retries · inicial + 3 retentativas
    assert sleeps == [0.0, 0.0, 0.0]


def test_server_error_retries_once_then_raises() -> None:
    """🇺🇸 A 5xx is retried once, after a fixed 1 s, then raises.

    🇧🇷 Um 5xx é retentado uma vez, após 1 s fixo, e então explode.
    """
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return _time_response(request)
        attempts["n"] += 1
        return _envelope_error("InternalServerError", status=500, trace_id="trace-5xx")

    sleeps: list[float] = []
    transport = _make_transport(client=_client(handler), sleep=sleeps.append)

    with pytest.raises(VaultError) as excinfo:
        transport.get(_WIDGET_PATH)

    assert attempts["n"] == 2
    assert sleeps == [1.0]
    assert excinfo.value.trace_id == "trace-5xx"


def test_session_seed_header_opens_and_reaches_on_seed() -> None:
    """🇺🇸 A valid `X-Session-Seed`, sealed with the session's `enc_key`, reaches `on_seed` as a 32-byte `SecretBox`.

    🇧🇷 Um `X-Session-Seed` válido, selado com o `enc_key` da sessão, chega a `on_seed` como um `SecretBox` de 32 bytes.
    """
    enc_key = secrets.token_bytes(32)
    session_id = "sess_1"
    seed = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    plaintext = json.dumps({"seed": b64url_encode(seed)}).encode("utf-8")
    ciphertext = AESGCM(enc_key).encrypt(nonce, plaintext, session_id.encode("utf-8"))
    header_value = f"{b64url_encode(nonce)}.{b64url_encode(ciphertext)}"

    keys = SessionKeys(
        session_id=session_id,
        sign_key=SecretBox.from_bytes(bytearray(secrets.token_bytes(32))),
        enc_key=SecretBox.from_bytes(bytearray(enc_key)),
        expires_at=9_999_999_999,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return _time_response(request)
        response = _envelope_success({"ok": True})
        response.headers["X-Session-Seed"] = header_value
        return response

    received: list[SecretBox] = []
    transport = _make_transport(client=_client(handler), session_keys=lambda: keys, on_seed=received.append)
    transport.get(_WIDGET_PATH)

    assert len(received) == 1
    assert isinstance(received[0], SecretBox)
    assert bytes(received[0].reveal()) == seed
    assert len(received[0]) == 32


def test_unsigned_request_has_no_signature_headers_or_session_dependency() -> None:
    """🇺🇸 `signed=False` sends no `X-Signature-*` headers and never calls `session_keys`.

    🇧🇷 `signed=False` não manda header `X-Signature-*` nenhum e nunca chama `session_keys`.
    """
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return _envelope_success({"enrollment_id": "e1"}, status=201)

    def _must_not_be_called() -> SessionKeys | None:
        raise AssertionError("session_keys must not be consulted for signed=False")

    transport = _make_transport(client=_client(handler), session_keys=_must_not_be_called)
    result = transport.post(
        "/api/external/v1/workspaces/ws_1/session/registry",
        json={"public_keys": {}},
        signed=False,
    )

    assert result == {"enrollment_id": "e1"}
    assert "x-signature-hmac" not in seen_headers
    assert "x-signature-nonce" not in seen_headers
    assert "x-signature-timestamp" not in seen_headers
    assert seen_headers["authorization"] == "Bearer apikey-test"


def test_upload_bytes_puts_directly_and_returns_the_etag() -> None:
    """🇺🇸 `upload_bytes` `PUT`s with no `Authorization`/signature and returns `ETag`.

    🇧🇷 `upload_bytes` faz `PUT` sem `Authorization`/assinatura e retorna o `ETag`.
    """
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, headers={"ETag": '"abc123"'})

    transport = _make_transport(client=_dummy_client(), storage_client=_client(handler))
    etag = transport.upload_bytes("https://r2.example.test/object", b"hello world", {"Content-Length": "11"})

    assert etag == '"abc123"'
    assert "authorization" not in seen_headers
    assert "x-signature-hmac" not in seen_headers


def test_download_bytes_returns_the_body_on_success() -> None:
    """🇺🇸 `download_bytes` buffers the whole R2 body. 🇧🇷 `download_bytes` junta o corpo inteiro do R2."""
    transport = _make_transport(
        client=_dummy_client(),
        storage_client=_client(lambda r: httpx.Response(200, content=b"the-bytes")),
    )
    assert transport.download_bytes("https://r2.example.test/object") == b"the-bytes"


def test_download_bytes_403_raises_storage_error() -> None:
    """🇺🇸 A non-2xx from R2 becomes `VaultError(code="StorageError")`.

    🇧🇷 Um não-2xx do R2 vira `VaultError(code="StorageError")`.
    """
    transport = _make_transport(
        client=_dummy_client(),
        storage_client=_client(lambda r: httpx.Response(403, text="Forbidden")),
    )
    with pytest.raises(VaultError) as excinfo:
        transport.download_bytes("https://r2.example.test/object")
    assert excinfo.value.code == "StorageError"
    assert excinfo.value.status == 403


def test_download_stream_yields_chunks_without_signing() -> None:
    """🇺🇸 `download_stream` yields body chunks with no `Authorization` header.

    🇧🇷 `download_stream` entrega pedaços do corpo sem header `Authorization`.
    """
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, content=b"streamed-bytes")

    transport = _make_transport(client=_dummy_client(), storage_client=_client(handler))
    assembled = b"".join(transport.download_stream("https://r2.example.test/object"))

    assert assembled == b"streamed-bytes"
    assert "authorization" not in seen_headers
