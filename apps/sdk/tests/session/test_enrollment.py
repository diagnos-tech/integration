"""🇺🇸 `enroll()`: the registration → prompt → poll → open-sealed-material dance.

Each test drives a real `httpx.Client` bound to `httpx.MockTransport`,
through the real `VaultTransport`, exactly like `transport/test_http.py` —
so a bug in how `enroll()` builds paths or reads the envelope shows up the
same way it would against the real vault. Sealing plays the vault's own
role: `seal_hybrid` targets the test's own `HybridKeyPair` public keys, the
same pair passed to `enroll()`, so `open_hybrid` inside `enroll()` opens it
for real.

🇧🇷 `enroll()`: a dança de registro → prompt → poll → abertura do material selado.

Cada teste roda um `httpx.Client` de verdade preso a `httpx.MockTransport`,
através do `VaultTransport` real, igual a `transport/test_http.py` — assim
um bug em como `enroll()` monta paths ou lê o envelope aparece do mesmo
jeito que apareceria contra o cofre de verdade. A selagem faz o papel do
próprio cofre: `seal_hybrid` mira as chaves públicas do `HybridKeyPair` do
teste, o mesmo par passado a `enroll()`, então o `open_hybrid` dentro de
`enroll()` abre de verdade.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable, Mapping

import httpx
import pytest
from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.hybrid import HybridKeyPair, seal_hybrid
from diagnos.errors import CryptoError, EnrollmentDeniedError, EnrollmentExpiredError
from diagnos.session.enrollment import EnrollmentPrompt, enroll
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
_REGISTRY_PATH = "/api/external/v1/workspaces/ws_1/session/registry"


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    """🇺🇸 An `httpx.Client` wired to a `MockTransport` instead of a socket.

    🇧🇷 Um `httpx.Client` ligado a um `MockTransport` em vez de um socket.
    """
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://vault.example.test")


def _make_transport(handler: Callable[[httpx.Request], httpx.Response]) -> VaultTransport:
    """🇺🇸 A `VaultTransport` whose signed side never gets exercised by enrollment.

    🇧🇷 Um `VaultTransport` cujo lado assinado nunca é exercitado pelo enrollment.
    """
    settings = Settings(api_token="apikey-test", vault_url="https://vault.example.test")  # noqa: S106 — fixture, not a real secret
    return VaultTransport(
        settings,
        _TOKEN,
        session_keys=lambda: None,
        client=_client(handler),
        storage_client=_client(lambda r: httpx.Response(200)),
        sleep=lambda seconds: None,
    )


def _envelope_success(result: object, status: int = 201) -> httpx.Response:
    """🇺🇸 A `success: true` envelope carrying `result`. 🇧🇷 Um envelope `success: true` carregando `result`."""
    return httpx.Response(
        status,
        json={"success": True, "status": "success", "status_code": status, "result": result, "docs": "d"},
    )


def _envelope_error(code: str, *, status: int, message: str = "boom") -> httpx.Response:
    """🇺🇸 A `success: false` envelope carrying one error `code`.

    🇧🇷 Um envelope `success: false` carregando um `code` de erro.
    """
    return httpx.Response(
        status,
        json={
            "success": False,
            "status": "error" if status >= 500 else "fail",
            "status_code": status,
            "errors": [{"code": code, "message": message, "trace_id": None}],
            "docs": "d",
        },
    )


def _registration_response(*, expires_at: int, poll_interval_seconds: float = 0.0) -> httpx.Response:
    """🇺🇸 The `201` body `POST session/registry` answers with.

    🇧🇷 O corpo `201` com que `POST session/registry` responde.
    """
    return _envelope_success(
        {
            "enrollment_id": "enr_1",
            "code": "123456",
            "approval_url": "https://vault.example.test/approve/enr_1",
            "expires_at": expires_at,
            "poll_interval_seconds": poll_interval_seconds,
        }
    )


def _sealed_session_dict(
    keypair: HybridKeyPair, enrollment_id: str, *, sign_key: bytes, enc_key: bytes
) -> dict[str, str]:
    """🇺🇸 Seals a `sealed_session` payload the way the vault would, to `keypair`'s own public keys.

    🇧🇷 Sela um payload de `sealed_session` do jeito que o cofre faria, para as próprias públicas de `keypair`.
    """
    plaintext = json.dumps(
        {
            "session_id": "sess_1",
            "sign_key": b64url_encode(sign_key),
            "enc_key": b64url_encode(enc_key),
            "expires_at": 9_999_999_999,
        }
    ).encode("utf-8")
    return seal_hybrid(keypair.x25519_public, keypair.mlkem768_public, plaintext, enrollment_id).to_dict()


def _sealed_group_key_dict(keypair: HybridKeyPair, enrollment_id: str, dek: bytes) -> dict[str, str]:
    """🇺🇸 Seals a raw group DEK the way the web app would (`docs/PROTOCOL.md §5`).

    🇧🇷 Sela uma DEK de grupo crua do jeito que o app web faria (`docs/PROTOCOL.md §5`).
    """
    return seal_hybrid(keypair.x25519_public, keypair.mlkem768_public, dek, enrollment_id).to_dict()


def test_happy_path_returns_a_keyring_and_prompts_once() -> None:
    """🇺🇸 registry → pending → approved unwraps into a `Keyring` with 32-byte keys and DEKs.

    🇧🇷 registry → pending → approved desembrulha num `Keyring` com chaves e DEKs de 32 bytes.
    """
    keypair = HybridKeyPair.generate()
    sign_key = secrets.token_bytes(32)
    enc_key = secrets.token_bytes(32)
    group_dek = secrets.token_bytes(32)
    seen_headers: list[Mapping[str, str]] = []
    poll_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(request.headers))
        if request.url.path == _REGISTRY_PATH and request.method == "POST":
            return _registration_response(expires_at=1_700_001_000)
        if request.url.path == f"{_REGISTRY_PATH}/enr_1" and request.method == "GET":
            poll_calls["n"] += 1
            if poll_calls["n"] == 1:
                return _envelope_success({"status": "pending"}, status=200)
            return _envelope_success(
                {
                    "status": "approved",
                    "approval": {
                        "session_id": "sess_1",
                        "session_expires_at": 9_999_999_999,
                        "sealed_session": _sealed_session_dict(keypair, "enr_1", sign_key=sign_key, enc_key=enc_key),
                        "sealed_group_keys": {"sg1": _sealed_group_key_dict(keypair, "enr_1", group_dek)},
                    },
                },
                status=200,
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    transport = _make_transport(handler)
    prompts: list[EnrollmentPrompt] = []
    sleeps: list[float] = []

    keyring = enroll(
        transport,
        _TOKEN,
        keypair,
        on_prompt=prompts.append,
        sleep=sleeps.append,
        now=lambda: 1_700_000_000.0,
    )

    assert keyring.enrollment_id == "enr_1"
    assert keyring.session.session_id == "sess_1"
    assert bytes(keyring.session.sign_key.reveal()) == sign_key
    assert bytes(keyring.session.enc_key.reveal()) == enc_key
    assert keyring.session.expires_at == 9_999_999_999
    assert bytes(keyring.group_key("sg1").reveal()) == group_dek

    assert len(prompts) == 1
    assert prompts[0] == EnrollmentPrompt(
        enrollment_id="enr_1",
        approval_url="https://vault.example.test/approve/enr_1",
        code="123456",
        expires_at=1_700_001_000,
    )
    assert poll_calls["n"] == 2
    assert sleeps == [0.0]  # 🇺🇸/🇧🇷 one sleep, for the single "pending" · um sleep, para o único "pending"

    for headers in seen_headers:
        assert "x-signature-hmac" not in headers
        assert "x-signature-nonce" not in headers
        assert "x-signature-timestamp" not in headers
        assert headers["authorization"] == "Bearer apikey-test"


def test_denied_raises_enrollment_denied_error() -> None:
    """🇺🇸 A `"denied"` poll status raises `EnrollmentDeniedError`.

    🇧🇷 Um status de poll `"denied"` lança `EnrollmentDeniedError`.
    """
    keypair = HybridKeyPair.generate()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == _REGISTRY_PATH and request.method == "POST":
            return _registration_response(expires_at=1_700_001_000)
        return _envelope_success({"status": "denied"}, status=200)

    transport = _make_transport(handler)
    with pytest.raises(EnrollmentDeniedError):
        enroll(
            transport,
            _TOKEN,
            keypair,
            on_prompt=lambda prompt: None,
            sleep=lambda seconds: None,
            now=lambda: 1_700_000_000.0,
        )


def test_expiry_via_local_clock_raises_before_polling_again() -> None:
    """🇺🇸 Once `now()` reaches `expires_at`, `enroll()` raises without polling again.

    🇧🇷 Assim que `now()` alcança `expires_at`, `enroll()` lança sem fazer novo poll.
    """
    keypair = HybridKeyPair.generate()
    poll_calls = {"n": 0}
    now_values = iter([500.0, 1_500.0])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == _REGISTRY_PATH and request.method == "POST":
            return _registration_response(expires_at=1_000)
        poll_calls["n"] += 1
        return _envelope_success({"status": "pending"}, status=200)

    transport = _make_transport(handler)
    with pytest.raises(EnrollmentExpiredError):
        enroll(
            transport,
            _TOKEN,
            keypair,
            on_prompt=lambda prompt: None,
            sleep=lambda seconds: None,
            now=lambda: next(now_values),
        )

    # 🇺🇸/🇧🇷 one "pending" poll happened before the second `now()` tripped the deadline.
    assert poll_calls["n"] == 1


def test_expiry_via_vault_not_found_after_deadline() -> None:
    """🇺🇸 A `404 SdkEnrollmentNotFound` from the poll also raises `EnrollmentExpiredError`.

    🇧🇷 Um `404 SdkEnrollmentNotFound` do poll também lança `EnrollmentExpiredError`.
    """
    keypair = HybridKeyPair.generate()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == _REGISTRY_PATH and request.method == "POST":
            return _registration_response(expires_at=1_700_001_000)
        return _envelope_error("SdkEnrollmentNotFound", status=404)

    transport = _make_transport(handler)
    with pytest.raises(EnrollmentExpiredError):
        enroll(
            transport,
            _TOKEN,
            keypair,
            on_prompt=lambda prompt: None,
            sleep=lambda seconds: None,
            now=lambda: 1_700_000_000.0,
        )


def test_wrong_size_group_dek_raises_crypto_error() -> None:
    """🇺🇸 A `sealed_group_keys[sg]` that opens to the wrong length raises `CryptoError`.

    🇧🇷 Um `sealed_group_keys[sg]` que abre com tamanho errado lança `CryptoError`.
    """
    keypair = HybridKeyPair.generate()
    sign_key = secrets.token_bytes(32)
    enc_key = secrets.token_bytes(32)
    wrong_size_dek = secrets.token_bytes(16)  # 🇺🇸/🇧🇷 16, not the required 32 bytes

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == _REGISTRY_PATH and request.method == "POST":
            return _registration_response(expires_at=1_700_001_000)
        return _envelope_success(
            {
                "status": "approved",
                "approval": {
                    "session_id": "sess_1",
                    "session_expires_at": 9_999_999_999,
                    "sealed_session": _sealed_session_dict(keypair, "enr_1", sign_key=sign_key, enc_key=enc_key),
                    "sealed_group_keys": {"sg1": _sealed_group_key_dict(keypair, "enr_1", wrong_size_dek)},
                },
            },
            status=200,
        )

    transport = _make_transport(handler)
    with pytest.raises(CryptoError):
        enroll(
            transport,
            _TOKEN,
            keypair,
            on_prompt=lambda prompt: None,
            sleep=lambda seconds: None,
            now=lambda: 1_700_000_000.0,
        )
