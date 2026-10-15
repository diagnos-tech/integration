"""🇺🇸 Enrollment and lock (`docs/PROTOCOL.md §5`): how an SDK process earns, and ends, a session.

Every test runs the SDK's real `enroll()` — registration, prompt, poll,
opening the sealed material with the SDK's own private keys — against the
Pact mock. The approval is sealed to a fixed SDK identity (`_crypto.py`), so
the contract carries real ciphertext and still never changes between runs.

🇧🇷 Enrollment e lock (`docs/PROTOCOL.md §5`): como um processo do SDK conquista, e encerra, uma sessão.

Todo teste roda o `enroll()` de verdade do SDK — registro, prompt, poll,
abertura do material selado com as próprias privadas do SDK — contra o mock
do Pact. A aprovação é selada para uma identidade fixa do SDK (`_crypto.py`),
então o contrato leva ciphertext de verdade e ainda assim nunca muda entre
rodadas.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from pact import Pact, match

from diagnos import EnrollmentDeniedError, EnrollmentExpiredError, EnrollmentPrompt
from diagnos.crypto.secure import SecretBox
from diagnos.session.enrollment import enroll
from diagnos.session.manager import SessionManager
from diagnos.transport.config import Settings

from _crypto import b64url, fixed_bytes, sdk_keypair, seal_to
from _enrollment import (
    ENROLLMENT_ID,
    EXPIRES_AT,
    POLL,
    POLL_EXPRESSION,
    POLL_PATTERN,
    clock,
    pin_runtime,
    poll,
    register,
)
from _identity import credential, identity_headers
from _wire import (
    EXTERNAL_PREFIX,
    SECURITY_GROUP_ID,
    SESSION_ID,
    WORKSPACE_ID,
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


def _approval() -> dict[str, object]:
    """🇺🇸 A real approval: the session and one group DEK, sealed to the fixed SDK identity (AAD = enrollment id).

    🇧🇷 Uma aprovação de verdade: a sessão e uma DEK de grupo, seladas para a identidade fixa do SDK (AAD = id).
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


def test_enrollment_approved_opens_the_session_and_group_keys(pact: Pact) -> None:
    """🇺🇸 Register → approved poll → the SDK opens both sealed payloads into a usable `Keyring`.

    🇧🇷 Registro → poll aprovado → o SDK abre os dois payloads selados num `Keyring` utilizável.
    """
    register(pact)
    poll(
        pact,
        state="an admin approved the enrollment for one security group",
        description="an SDK process polls an enrollment an admin approved",
        status=200,
        body=ok(_approval()),
    )
    prompts: list[EnrollmentPrompt] = []

    with pact.serve() as server:
        keyring = enroll(
            make_transport(str(server.url), signed=False),
            credential(),
            sdk_keypair(),
            on_prompt=prompts.append,
            sleep=lambda seconds: None,
            now=lambda: EXPIRES_AT - 60,
        )

    assert [prompt.code for prompt in prompts] == ["482915"]
    assert keyring.enrollment_id == ENROLLMENT_ID
    assert keyring.session.session_id == SESSION_ID
    assert keyring.security_group_ids == [SECURITY_GROUP_ID]
    assert bytes(keyring.group_key(SECURITY_GROUP_ID).reveal()) == fixed_bytes("group/dek")


def test_enrollment_still_pending_keeps_polling_until_it_expires(pact: Pact) -> None:
    """🇺🇸 `pending` means "ask again later"; past `expires_at` the SDK gives up with `EnrollmentExpiredError`.

    🇧🇷 `pending` significa "pergunte de novo depois"; passado `expires_at` o SDK desiste com `EnrollmentExpiredError`.
    """
    register(pact)
    poll(
        pact,
        state="an enrollment is waiting for an admin",
        description="an SDK process polls an enrollment nobody has approved yet",
        status=200,
        body=ok({"status": literal("pending")}),
    )

    with pact.serve() as server, pytest.raises(EnrollmentExpiredError):
        enroll(
            make_transport(str(server.url), signed=False),
            credential(),
            sdk_keypair(),
            on_prompt=lambda prompt: None,
            sleep=lambda seconds: None,
            now=clock(EXPIRES_AT - 60, EXPIRES_AT - 60, EXPIRES_AT + 1),
        )


def test_enrollment_denied_raises(pact: Pact) -> None:
    """🇺🇸 `denied` is final: the SDK raises `EnrollmentDeniedError` instead of polling again.

    🇧🇷 `denied` é final: o SDK lança `EnrollmentDeniedError` em vez de fazer poll de novo.
    """
    register(pact)
    poll(
        pact,
        state="an admin denied the enrollment",
        description="an SDK process polls an enrollment an admin denied",
        status=200,
        body=ok({"status": literal("denied")}),
    )

    with pact.serve() as server, pytest.raises(EnrollmentDeniedError):
        enroll(
            make_transport(str(server.url), signed=False),
            credential(),
            sdk_keypair(),
            on_prompt=lambda prompt: None,
            sleep=lambda seconds: None,
            now=lambda: EXPIRES_AT - 60,
        )


def test_enrollment_the_vault_forgot_is_treated_as_expired(pact: Pact) -> None:
    """🇺🇸 A `404` on poll means the vault already dropped the enrollment — the approval window is closed.

    🇧🇷 Um `404` no poll significa que o cofre já descartou o enrollment — a janela de aprovação fechou.
    """
    register(pact)
    name, params = workspace_state("the vault no longer knows the enrollment", enrollment_id=ENROLLMENT_ID)
    (
        pact.upon_receiving("an SDK process polls an enrollment that no longer exists")
        .given(name, params)
        .with_request("GET", path(POLL, pattern=POLL_PATTERN, expression=POLL_EXPRESSION))
        .with_headers(identity_headers())
        .will_respond_with(404)
        .with_body(failure("SdkEnrollmentNotFound"), content_type="application/json")
    )

    with pact.serve() as server, pytest.raises(EnrollmentExpiredError):
        enroll(
            make_transport(str(server.url), signed=False),
            credential(),
            sdk_keypair(),
            on_prompt=lambda prompt: None,
            sleep=lambda seconds: None,
            now=lambda: EXPIRES_AT - 60,
        )


def test_lock_ends_the_session_on_the_vault(pact: Pact) -> None:
    """🇺🇸 `lock()` sends a signed `POST session/lock`; the response's `random_seed` still reaches the SDK's entropy.

    `SessionManager.lock()` is best-effort by design and swallows errors, so
    the request itself is asserted by Pact: every interaction must have been
    matched when `serve()` exits.

    🇧🇷 `lock()` manda um `POST session/lock` assinado; o `random_seed` da resposta ainda chega à entropia do SDK.

    `SessionManager.lock()` é best-effort por desenho e engole erros, então a
    requisição em si é conferida pelo Pact: toda interação precisa ter sido
    casada quando `serve()` sai.
    """
    declare_clock(pact)
    (
        pact.upon_receiving("an SDK process ends its session")
        .given("an SDK session is active", {"workspace_id": WORKSPACE_ID})
        .with_request("POST", f"{EXTERNAL_PREFIX}/session/lock")
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body({"success": True, **seed(label="lock")}, content_type="application/json")
    )
    seeds: list[SecretBox] = []

    with pact.serve() as server:
        transport = make_transport(str(server.url), on_seed=seeds.append)
        identity = credential()
        SessionManager(Settings(credential=identity, vault_url=str(server.url)), identity, transport).lock()

    assert [bytes(box.reveal()) for box in seeds] == [fixed_bytes("lock/seed")]
