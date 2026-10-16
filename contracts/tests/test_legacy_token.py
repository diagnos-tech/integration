"""🇺🇸 The deprecated `apikey-` token, still accepted until 2027-04-15: enrollment with a human approval, and lock.

A service account token needs none of this (`test_session.py`). The legacy
bearer must keep enrolling and locking exactly as SDK `0.1.0` did, so a
process still on the old token keeps working through the deprecation
window. Every test runs the SDK's real `enroll()` — registration, prompt,
poll, opening the sealed material with the SDK's own private keys.

🇧🇷 O token `apikey-` obsoleto, ainda aceito até 2027-04-15: enrollment com aprovação humana, e lock.

Um token de conta de serviço não precisa de nada disto (`test_session.py`).
O bearer legado precisa continuar fazendo enrollment e lock exatamente como
o SDK `0.1.0` fazia, para um processo ainda no token antigo seguir
funcionando durante a janela de depreciação. Todo teste roda o `enroll()` de
verdade do SDK — registro, prompt, poll, abertura do material selado com as
próprias privadas do SDK.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator

import pytest
from pact import Pact, match

from diagnos import EnrollmentDeniedError, EnrollmentExpiredError, EnrollmentPrompt
from diagnos.session.enrollment import enroll
from diagnos.session.keyring import Keyring
from diagnos.session.manager import SessionManager
from diagnos.transport.config import Settings

from _crypto import b64url, fixed_bytes, sdk_keypair, seal_to
from _enrollment import (
    ENROLLMENT_ID,
    EXPIRES_AT,
    LEGACY,
    POLL,
    POLL_EXPRESSION,
    POLL_PATTERN,
    clock,
    pin_runtime,
    poll,
    register,
)
from _wire import (
    API_TOKEN,
    EXTERNAL_PREFIX,
    SECURITY_GROUP_ID,
    SESSION_ID,
    TOKEN,
    WORKSPACE_ID,
    bearer_header,
    declare_clock,
    encrypted,
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


def _enroll(
    url: str,
    *,
    on_prompt: Callable[[EnrollmentPrompt], None] = lambda prompt: None,
    now: Callable[[], float] = lambda: EXPIRES_AT - 60,
) -> Keyring:
    """🇺🇸 The SDK's real `enroll()` with the legacy bearer, no sleeping. 🇧🇷 O `enroll()` real com o bearer legado."""
    transport = make_transport(url, signed=False, legacy=True)
    return enroll(transport, TOKEN, sdk_keypair(), on_prompt=on_prompt, sleep=lambda seconds: None, now=now)


def _approval() -> dict[str, object]:
    """🇺🇸 A real approval: the session and one group key, sealed to the fixed SDK identity (AAD = enrollment id).

    🇧🇷 Uma aprovação de verdade: a sessão e uma chave de grupo, seladas para a identidade fixa do SDK (AAD = id).
    """
    keypair = sdk_keypair()
    session_plaintext = json.dumps(
        {
            "session_id": SESSION_ID,
            "sign_key": b64url(fixed_bytes("session/sign-key")),
            "enc_key": b64url(fixed_bytes("session/enc-key")),
            "expires_at": 1_780_086_400,
        },
        separators=(",", ":"),
    ).encode()
    sealed_session = seal_to(keypair, session_plaintext, ENROLLMENT_ID, label="approval/session")
    sealed_group_key = seal_to(keypair, fixed_bytes("group/dek"), ENROLLMENT_ID, label="approval/group-key")
    return {
        "status": literal("approved"),
        "approval": {
            "sealed_session": encrypted(sealed_session),
            "sealed_group_keys": match.each_value_matches(
                {SECURITY_GROUP_ID: sealed_group_key},
                rules=match.like({"salt": "salt", "nonce": "nonce", "ciphertext": "ciphertext"}),
            ),
        },
    }


def test_a_legacy_token_enrolls_and_opens_the_approved_session(pact: Pact) -> None:
    """🇺🇸 Register → approved poll → the SDK opens both sealed payloads into a usable `Keyring`.

    🇧🇷 Registro → poll aprovado → o SDK abre os dois payloads selados num `Keyring` utilizável.
    """
    register(pact)
    poll(
        pact,
        state="an admin approved the enrollment for one security group",
        description=f"an SDK process {LEGACY}polls an enrollment an admin approved",
        status=200,
        body=ok(_approval()),
    )
    prompts: list[EnrollmentPrompt] = []

    with pact.serve() as server:
        keyring = _enroll(str(server.url), on_prompt=prompts.append)

    assert [prompt.code for prompt in prompts] == ["482915"]
    assert keyring.session.session_id == SESSION_ID
    assert bytes(keyring.group_key(SECURITY_GROUP_ID).reveal()) == fixed_bytes("group/dek")


def test_a_legacy_enrollment_still_pending_keeps_polling_until_it_expires(pact: Pact) -> None:
    """🇺🇸 `pending` means "ask again later"; past `expires_at` the SDK gives up with `EnrollmentExpiredError`.

    🇧🇷 `pending` significa "pergunte de novo depois"; passado `expires_at` o SDK desiste com `EnrollmentExpiredError`.
    """
    register(pact)
    poll(
        pact,
        state="an enrollment opened with a legacy apikey- token is waiting for an admin",
        description=f"an SDK process {LEGACY}polls an enrollment nobody has approved yet",
        status=200,
        body=ok({"status": literal("pending")}),
    )

    with pact.serve() as server, pytest.raises(EnrollmentExpiredError):
        _enroll(str(server.url), now=clock(EXPIRES_AT - 60, EXPIRES_AT - 60, EXPIRES_AT + 1))


def test_a_denied_legacy_enrollment_raises(pact: Pact) -> None:
    """🇺🇸 `denied` is final: `EnrollmentDeniedError` instead of polling again. 🇧🇷 `denied` é final."""
    register(pact)
    poll(
        pact,
        state="an admin denied the enrollment",
        description=f"an SDK process {LEGACY}polls an enrollment an admin denied",
        status=200,
        body=ok({"status": literal("denied")}),
    )

    with pact.serve() as server, pytest.raises(EnrollmentDeniedError):
        _enroll(str(server.url))


def test_a_legacy_enrollment_the_vault_forgot_is_treated_as_expired(pact: Pact) -> None:
    """🇺🇸 A `404` on poll means the vault already dropped the enrollment — the approval window is closed.

    🇧🇷 Um `404` no poll significa que o cofre já descartou o enrollment — a janela de aprovação fechou.
    """
    register(pact)
    name, params = workspace_state("the vault no longer knows the enrollment", enrollment_id=ENROLLMENT_ID)
    (
        pact.upon_receiving(f"an SDK process {LEGACY}polls an enrollment that no longer exists")
        .given(name, params)
        .with_request("GET", path(POLL, pattern=POLL_PATTERN, expression=POLL_EXPRESSION))
        .with_headers(bearer_header())
        .will_respond_with(404)
        .with_body(failure("SdkEnrollmentNotFound"), content_type="application/json")
    )

    with pact.serve() as server, pytest.raises(EnrollmentExpiredError):
        _enroll(str(server.url))


def test_a_legacy_token_still_locks_its_session(pact: Pact) -> None:
    """🇺🇸 Bearer plus the session HMAC on `/session/lock`, exactly as 0.1.0 sent it. 🇧🇷 Como na 0.1.0."""
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
