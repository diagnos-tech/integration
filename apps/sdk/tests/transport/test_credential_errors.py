"""🇺🇸 The vault's `Credential*` codes: typed exceptions, actionable messages, and the transport's retry rules.

🇧🇷 Os códigos `Credential*` do cofre: exceções tipadas, mensagens acionáveis, e as regras de retentativa do transporte.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from _tokens import parsed

from diagnos.errors import (
    AuthenticationError,
    ClockSkewError,
    CredentialError,
    CredentialExpiredError,
    CredentialReplayError,
    CredentialRevokedError,
    CredentialSignatureError,
    CredentialUnknownError,
    DiagnosPermissionError,
    ScopeMissingError,
    ValidationError,
    WorkspaceMismatchError,
)
from diagnos.transport.config import Settings
from diagnos.transport.credential_failures import credential_error
from diagnos.transport.envelope import unwrap_result
from diagnos.transport.http import VaultTransport


def failure(code: str, status: int, details: dict[str, Any] | None = None, **headers: str) -> httpx.Response:
    """🇺🇸 The vault's error envelope. 🇧🇷 O envelope de erro do cofre."""
    error: dict[str, Any] = {"code": code, "message": "recusado", "trace_id": "tr_1"}
    if details is not None:
        error["details"] = details
    return httpx.Response(status, json={"success": False, "errors": [error]}, headers=headers)


@pytest.mark.parametrize(
    ("code", "status", "cls", "base", "advice"),
    [
        ("CredentialSignatureInvalid", 401, CredentialSignatureError, AuthenticationError, "diagnos login"),
        ("CredentialReplayed", 401, CredentialReplayError, AuthenticationError, "not retried"),
        ("CredentialKeyRevoked", 401, CredentialRevokedError, AuthenticationError, "Create a new token"),
        ("CredentialKeyExpired", 401, CredentialExpiredError, AuthenticationError, "expiry"),
        ("CredentialKeyUnknown", 401, CredentialUnknownError, AuthenticationError, "DIAGNOS_VAULT_URL"),
        ("CredentialWorkspaceMismatch", 403, WorkspaceMismatchError, DiagnosPermissionError, "target workspace"),
        ("CredentialScopeMissing", 403, ScopeMissingError, DiagnosPermissionError, "a new token"),
        ("CredentialClockSkew", 401, ClockSkewError, AuthenticationError, "NTP"),
    ],
)
def test_each_code_becomes_its_typed_exception_with_advice(
    code: str, status: int, cls: type[CredentialError], base: type[Exception], advice: str
) -> None:
    """🇺🇸 Class, its 401/403 parent, the vault's message and the SDK's advice, both languages.

    🇧🇷 Classe, o pai 401/403, a mensagem do cofre e o conselho do SDK, nos dois idiomas.
    """
    with pytest.raises(cls) as caught:
        unwrap_result(failure(code, status))
    error = caught.value
    assert isinstance(error, base)
    assert isinstance(error, CredentialError)
    assert (error.code, error.status, error.trace_id) == (code, status, "tr_1")
    assert error.message.startswith("recusado — 🇺🇸")
    assert advice in error.message
    assert "🇧🇷" in error.message


@pytest.mark.parametrize(
    "server_time",
    [1_760_000_000, 1_760_000_000_000, "1760000000", "2025-10-09T08:53:20Z", "2025-10-09T08:53:20"],
)
def test_clock_skew_shows_the_difference_from_server_time(server_time: object) -> None:
    """🇺🇸 Seconds, milliseconds, numeric strings and ISO 8601 all give the same 93 s. 🇧🇷 Todos dão os mesmos 93 s."""
    response = failure("CredentialClockSkew", 401, {"server_time": server_time})
    error = credential_error(
        "CredentialClockSkew",
        "",
        response=response,
        details={"server_time": server_time},
        trace_id=None,
        now=1_760_000_093,
    )
    assert isinstance(error, ClockSkewError)
    assert error.skew_seconds == pytest.approx(93)
    assert error.server_time == datetime.fromtimestamp(1_760_000_000, UTC)
    assert "93 s ahead of the vault" in error.message
    assert "93 s adiantado" in error.message


def test_clock_skew_falls_back_to_the_date_header_and_then_to_no_number() -> None:
    """🇺🇸 `Date` when `server_time` is absent or unreadable; a plain sentence when neither exists.

    🇧🇷 `Date` quando `server_time` falta ou é ilegível; uma frase simples quando nenhum existe.
    """
    dated = failure("CredentialClockSkew", 401, Date="Thu, 09 Oct 2025 08:53:20 GMT")
    for details in ({}, {"server_time": "yesterday"}, {"server_time": True}, {"server_time": [1]}):
        error = credential_error(
            "CredentialClockSkew", "", response=dated, details=details, trace_id=None, now=1_759_999_950
        )
        assert isinstance(error, ClockSkewError)
        assert error.skew_seconds == pytest.approx(-50)
        assert "50 s behind the vault" in error.message
    for header in ({}, {"Date": "not a date"}):
        bare = credential_error(
            "CredentialClockSkew",
            "",
            response=failure("CredentialClockSkew", 401, **header),
            details={},
            trace_id=None,
        )
        assert isinstance(bare, ClockSkewError)
        assert bare.skew_seconds is None
        assert "more than 60 s" in bare.message


def test_scope_missing_names_the_resource_action_and_group() -> None:
    """🇺🇸 `details.resource`/`action`/`security_group_id` reach the message and the attributes.

    🇧🇷 `details.resource`/`action`/`security_group_id` chegam à mensagem e aos atributos.
    """
    details = {"resource": "patients", "action": "write", "security_group_id": "sg_9"}
    with pytest.raises(ScopeMissingError) as caught:
        unwrap_result(failure("CredentialScopeMissing", 403, details))
    error = caught.value
    assert (error.resource, error.action, error.security_group_id) == ("patients", "write", "sg_9")
    assert "lacks the permission 'write' on 'patients' in security group 'sg_9'" in error.message
    assert error.details == details
    for partial, expected in (({"action": "read"}, "permission 'read'."), ({}, "permission (unnamed).")):
        with pytest.raises(ScopeMissingError) as unnamed:
            unwrap_result(failure("CredentialScopeMissing", 403, partial))
        assert expected in unnamed.value.message


def test_other_codes_keep_their_status_class_and_now_carry_details() -> None:
    """🇺🇸 A non-credential code is untouched, plus `details`. 🇧🇷 Outro código segue igual, mais `details`."""
    with pytest.raises(ValidationError) as caught:
        unwrap_result(failure("InvalidBody", 400, {"field": "name"}))
    assert not isinstance(caught.value, CredentialError)
    assert caught.value.details == {"field": "name"}


def _transport(handler: Any) -> VaultTransport:
    """🇺🇸 A transport signing with a token minted now. 🇧🇷 Um transporte com um token criado agora."""
    token = parsed("wsT")
    return VaultTransport(
        Settings(token=token, vault_url="https://vault.test"),
        token,
        session_keys=lambda: None,
        client=httpx.Client(base_url="https://vault.test", transport=httpx.MockTransport(handler)),
        sleep=lambda seconds: None,
    )


def test_the_transport_signs_unsigned_calls_too_and_resyncs_once_on_clock_skew() -> None:
    """🇺🇸 Identity on a call with no session yet, `/time` before the first signature, one resync on skew.

    🇧🇷 Identidade numa chamada ainda sem sessão, `/time` antes da 1ª assinatura, uma ressincronização no relógio.
    """
    seen: list[httpx.Request] = []
    answers = iter([failure("CredentialClockSkew", 401), httpx.Response(200, json={"success": True, "result": 7})])

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/time":
            return httpx.Response(200, json={"result": 1_760_000_000_000})
        assert "Authorization" not in request.headers
        assert request.headers["Content-Digest"].startswith("sha-256=:")
        return next(answers)

    assert _transport(handler).post("/api/external/v1/x", json={"a": 1}, signed=False) == 7
    paths = [request.url.path for request in seen]
    assert paths == ["/time"] * 3 + ["/api/external/v1/x"] + ["/time"] * 3 + ["/api/external/v1/x"]
    first, second = (request for request in seen if request.url.path != "/time")
    assert first.headers["Signature-Input"] != second.headers["Signature-Input"]


def test_a_second_clock_skew_and_a_replay_are_raised_not_retried() -> None:
    """🇺🇸 Skew twice → `ClockSkewError`; a replay is never retried (the first copy may have landed).

    🇧🇷 Relógio duas vezes → `ClockSkewError`; replay nunca é retentado (a primeira cópia pode ter chegado).
    """
    for code, cls, calls in (
        ("CredentialClockSkew", ClockSkewError, 2),
        ("CredentialReplayed", CredentialReplayError, 1),
    ):
        attempts: list[int] = []

        def handler(request: httpx.Request, code: str = code, attempts: list[int] = attempts) -> httpx.Response:
            if request.url.path == "/time":
                return httpx.Response(200, json={"result": 1_760_000_000_000})
            attempts.append(1)
            return failure(code, 401)

        with pytest.raises(cls):
            _transport(handler).get("/api/external/v1/x", signed=False)
        assert len(attempts) == calls


def test_a_server_time_beside_errors_is_read_too() -> None:
    """🇺🇸 A top-level `server_time` feeds the skew. 🇧🇷 Um `server_time` no topo do envelope alimenta a diferença."""
    body = {
        "success": False,
        "server_time": 1_000_000_000,
        "errors": [{"code": "CredentialClockSkew", "message": ""}],
    }
    with pytest.raises(ClockSkewError) as caught:
        unwrap_result(httpx.Response(401, json=body))
    assert caught.value.server_time == datetime.fromtimestamp(1_000_000_000, UTC)
    assert caught.value.details == {"server_time": 1_000_000_000}
