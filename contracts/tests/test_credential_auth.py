"""🇺🇸 How the credential fails, and the deprecated `apikey-` token that still works until 2027-04-15.

A revoked key must surface as `CredentialRevokedError` with the fix in its
message; the legacy bearer must keep enrolling and locking exactly as
`0.1.0` did, so an SDK on the old token keeps working through the
deprecation window.

🇧🇷 Como a credencial falha, e o token `apikey-` obsoleto que ainda funciona até 2027-04-15.

Uma chave revogada precisa aparecer como `CredentialRevokedError` com a
correção na mensagem; o bearer legado precisa continuar fazendo enrollment e
lock exatamente como a `0.1.0` fazia, para um SDK no token antigo seguir
funcionando durante a janela de depreciação.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pact import Pact

from diagnos import CredentialRevokedError, EnrollmentExpiredError
from diagnos.session.enrollment import enroll
from diagnos.session.manager import SessionManager
from diagnos.transport.config import Settings

from _crypto import sdk_keypair
from _enrollment import (
    EXPIRES_AT,
    LEGACY,
    REGISTRY,
    REGISTRY_EXPRESSION,
    REGISTRY_PATTERN,
    clock,
    pin_runtime,
    poll,
    register,
)
from _identity import credential, identity_headers
from _wire import (
    API_TOKEN,
    EXTERNAL_PREFIX,
    TOKEN,
    WORKSPACE_ID,
    declare_clock,
    failure,
    literal,
    ok,
    path,
    seed,
    signed_headers,
    workspace_state,
)
from conftest import make_transport


@pytest.fixture(autouse=True)
def _fixed_runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """🇺🇸 Same request body on every machine (`_enrollment.pin_runtime`). 🇧🇷 Mesmo corpo em toda máquina."""
    pin_runtime(monkeypatch)
    yield


def test_a_revoked_key_cannot_open_an_enrollment(pact: Pact) -> None:
    """🇺🇸 `401 CredentialKeyRevoked` on registration becomes `CredentialRevokedError`, telling how to rotate.

    🇧🇷 `401 CredentialKeyRevoked` no registro vira `CredentialRevokedError`, dizendo como girar a chave.
    """
    declare_clock(pact)
    state, params = workspace_state("the service account's key was revoked")
    (
        pact.upon_receiving("an SDK process signs with a revoked key")
        .given(state, params)
        .with_request("POST", path(REGISTRY, pattern=REGISTRY_PATTERN, expression=REGISTRY_EXPRESSION))
        .with_headers(identity_headers(body=True))
        .will_respond_with(401)
        .with_body(failure("CredentialKeyRevoked"), content_type="application/json")
    )

    with pact.serve() as server, pytest.raises(CredentialRevokedError, match="Rotate key"):
        enroll(
            make_transport(str(server.url), signed=False),
            credential(),
            sdk_keypair(),
            on_prompt=lambda prompt: None,
            sleep=lambda seconds: None,
            now=lambda: EXPIRES_AT - 60,
        )


def test_a_legacy_token_still_enrolls_until_the_sunset(pact: Pact) -> None:
    """🇺🇸 The deprecated `apikey-` bearer still registers and polls (accepted until 2027-04-15), with no clock sync.

    🇧🇷 O bearer `apikey-` obsoleto ainda registra e faz poll (aceito até 2027-04-15), sem sincronizar relógio.
    """
    register(pact, legacy=True)
    poll(
        pact,
        state="an enrollment opened with a legacy apikey- token is waiting for an admin",
        description=f"an SDK process {LEGACY}polls an enrollment nobody has approved yet",
        status=200,
        body=ok({"status": literal("pending")}),
        legacy=True,
    )

    with pact.serve() as server, pytest.raises(EnrollmentExpiredError):
        enroll(
            make_transport(str(server.url), signed=False, legacy=True),
            TOKEN,
            sdk_keypair(),
            on_prompt=lambda prompt: None,
            sleep=lambda seconds: None,
            now=clock(EXPIRES_AT - 60, EXPIRES_AT - 60, EXPIRES_AT + 1),
        )


def test_a_legacy_token_still_locks_its_session(pact: Pact) -> None:
    """🇺🇸 Bearer plus the session HMAC, exactly as 0.1.0 sent it. 🇧🇷 Bearer mais o HMAC de sessão, como na 0.1.0."""
    declare_clock(pact)
    (
        pact.upon_receiving(f"an SDK process {LEGACY}ends its session")
        .given("an SDK session opened with a legacy apikey- token is active", {"workspace_id": WORKSPACE_ID})
        .with_request("POST", f"{EXTERNAL_PREFIX}/session/lock")
        .with_headers(signed_headers(legacy=True))
        .will_respond_with(200)
        .with_body({"success": True, **seed(label="lock")}, content_type="application/json")
    )

    with pact.serve() as server:
        transport = make_transport(str(server.url), legacy=True)
        SessionManager(Settings(api_token=API_TOKEN, vault_url=str(server.url)), TOKEN, transport).lock()
