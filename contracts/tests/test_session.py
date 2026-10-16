"""🇺🇸 The token's session (spec §5): one signed `POST …/session` opens it, `POST …/session/lock` ends it.

The answer is real ciphertext: the session and one group key, sealed to the
contract token's own X25519 + ML-KEM-768 pair with the reference's AADs, by
the independent oracles of `_crypto.py` — so the contract proves the SDK
opens what the vault seals, and still never changes between runs. On the
provider side, the state `a service account token can open a session`
creates a real key and the request filter re-signs with it, so the vault
seals to that key instead; only the shapes here are pinned.

🇧🇷 A sessão do token (spec §5): um `POST …/session` assinado a abre, `POST …/session/lock` a encerra.

A resposta é ciphertext de verdade: a sessão e uma chave de grupo, seladas
para o par X25519 + ML-KEM-768 do próprio token do contrato com os AADs da
referência, pelos oráculos independentes de `_crypto.py` — então o contrato
prova que o SDK abre o que o cofre sela, e ainda assim nunca muda entre
rodadas. Do lado do provider, o state `a service account token can open a
session` cria uma chave de verdade e o filtro de requisição reassina com ela,
então o cofre sela para essa chave; aqui só as formas são travadas.
"""

from __future__ import annotations

import json

import pytest
from pact import Pact, match

from diagnos import CredentialRevokedError
from diagnos.crypto.secure import SecretBox
from diagnos.session.manager import SessionManager
from diagnos.session.token_session import group_key_aad, open_token_session, session_aad
from diagnos.transport.config import Settings

from _crypto import b64url, fixed_bytes, seal_to
from _identity import identity_headers, token
from _wire import (
    EXTERNAL_PREFIX,
    SECURITY_GROUP_ID,
    SESSION_ID,
    WORKSPACE_ID,
    declare_clock,
    encrypted,
    failure,
    ok,
    path,
    seed,
    signed_headers,
    workspace_state,
)
from conftest import make_transport

EXPIRES_AT = 1_780_086_400
SESSION = f"{EXTERNAL_PREFIX}/workspaces/{WORKSPACE_ID}/session"
SESSION_PATTERN = rf"^{EXTERNAL_PREFIX}/workspaces/[^/]+/session$"
SESSION_EXPRESSION = f"{EXTERNAL_PREFIX}/workspaces/${{workspace_id}}/session"


def _opened() -> dict[str, object]:
    """🇺🇸 `OpenServiceAccountSessionResponse`, sealed to the contract token for real. 🇧🇷 Selada de verdade."""
    contract = token()
    pair = contract.keypair()
    plaintext = json.dumps(
        {
            "session_id": SESSION_ID,
            "sign_key": b64url(fixed_bytes("session/sign-key")),
            "enc_key": b64url(fixed_bytes("session/enc-key")),
            "expires_at": EXPIRES_AT,
        },
        separators=(",", ":"),
    ).encode()
    sealed_session = seal_to(pair, plaintext, session_aad(WORKSPACE_ID, contract.key_id), label="token/session")
    group_aad = group_key_aad(WORKSPACE_ID, contract.key_id, SECURITY_GROUP_ID)
    sealed_group = seal_to(pair, fixed_bytes("group/dek"), group_aad, label="token/group-key")
    return {
        "session_id": match.str(SESSION_ID),
        "expires_at": match.int(EXPIRES_AT),
        "sealed_session": encrypted(sealed_session),
        "sealed_group_keys": match.each_value_matches(
            {SECURITY_GROUP_ID: sealed_group},
            rules=match.like({"salt": "salt", "nonce": "nonce", "ciphertext": "ciphertext"}),
        ),
    }


def _declare_session(pact: Pact, *, state: str, description: str, status: int, body: dict[str, object]) -> None:
    """🇺🇸 `POST …/session`: no body, only the token's signature, answering `body`.

    🇧🇷 `POST …/session`: sem corpo, só a assinatura do token, respondendo `body`.
    """
    name, params = workspace_state(state)
    (
        pact.upon_receiving(description)
        .given(name, params)
        .with_request("POST", path(SESSION, pattern=SESSION_PATTERN, expression=SESSION_EXPRESSION))
        .with_headers(identity_headers())
        .will_respond_with(status)
        .with_body(body, content_type="application/json")
    )


def test_the_token_opens_a_session_and_the_keys_of_its_groups(pact: Pact) -> None:
    """🇺🇸 One signed POST; the SDK opens the sealed session and group key with the token's own pair.

    🇧🇷 Um POST assinado; o SDK abre a sessão e a chave de grupo seladas com o próprio par do token.
    """
    declare_clock(pact)
    _declare_session(
        pact,
        state="a service account token can open a session",
        description="an SDK process opens a session with its service account token",
        status=201,
        body=ok(_opened()),
    )

    contract = token()
    with pact.serve() as server:
        keyring = open_token_session(make_transport(str(server.url), signed=False), contract, contract.keypair())

    assert (keyring.session.session_id, keyring.session.expires_at) == (SESSION_ID, EXPIRES_AT)
    assert keyring.security_group_ids == [SECURITY_GROUP_ID]
    assert bytes(keyring.group_key(SECURITY_GROUP_ID).reveal()) == fixed_bytes("group/dek")


def test_a_revoked_token_cannot_open_a_session(pact: Pact) -> None:
    """🇺🇸 `401 CredentialKeyRevoked` becomes `CredentialRevokedError`, saying to create a new token.

    🇧🇷 `401 CredentialKeyRevoked` vira `CredentialRevokedError`, dizendo para criar um token novo.
    """
    declare_clock(pact)
    _declare_session(
        pact,
        state="the service account's key was revoked",
        description="an SDK process opens a session with a revoked service account token",
        status=401,
        body=failure("CredentialKeyRevoked"),
    )

    contract = token()
    with pact.serve() as server, pytest.raises(CredentialRevokedError, match="Create a new token"):
        open_token_session(make_transport(str(server.url), signed=False), contract, contract.keypair())


def test_lock_ends_the_tokens_session_on_its_workspace_route(pact: Pact) -> None:
    """🇺🇸 `lock()` sends a signed `POST …/workspaces/{ws}/session/lock`; the `random_seed` still reaches the SDK.

    `SessionManager.lock()` is best-effort and swallows errors, so the
    request itself is asserted by Pact: every interaction must have been
    matched when `serve()` exits.

    🇧🇷 `lock()` manda um `POST …/workspaces/{ws}/session/lock` assinado; o `random_seed` ainda chega ao SDK.

    `SessionManager.lock()` é best-effort e engole erros, então a requisição
    em si é conferida pelo Pact: toda interação precisa ter sido casada
    quando `serve()` sai.
    """
    declare_clock(pact)
    name, params = workspace_state("an SDK session is active")
    (
        pact.upon_receiving("an SDK process ends the session of its service account token")
        .given(name, params)
        .with_request(
            "POST",
            path(
                f"{SESSION}/lock",
                pattern=rf"^{EXTERNAL_PREFIX}/workspaces/[^/]+/session/lock$",
                expression=f"{SESSION_EXPRESSION}/lock",
            ),
        )
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body({"success": True, **seed(label="lock")}, content_type="application/json")
    )
    seeds: list[SecretBox] = []

    with pact.serve() as server:
        transport = make_transport(str(server.url), on_seed=seeds.append)
        contract = token()
        SessionManager(Settings(token=contract, vault_url=str(server.url)), contract, transport).lock()

    assert [bytes(box.reveal()) for box in seeds] == [fixed_bytes("lock/seed")]
