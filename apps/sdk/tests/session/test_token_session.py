"""🇺🇸 The session the token opens by itself (spec §5): one signed POST, seals bound by AAD, lock, and reopen.

A fake vault seals real material to the token's own X25519 + ML-KEM-768
pair — with the AADs the reference fixes — so every test exercises the
enclave opening seals, not a mock of it.

🇧🇷 A sessão que o token abre sozinho (spec §5): um POST assinado, selos presos pelo AAD, lock e reabertura.

Um cofre falso sela material de verdade para o próprio par X25519 +
ML-KEM-768 do token — com os AADs que a referência fixa — então todo teste
exercita o enclave abrindo selos, não um mock dele.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from _token_vault import GROUP_KEY, seal_to, session_answer
from _tokens import legacy_token, parsed

from diagnos.crypto.secure import SecretBox
from diagnos.errors import AuthenticationError, CryptoError, ProtocolError
from diagnos.session.keyring import SessionKeys
from diagnos.session.manager import SessionManager
from diagnos.session.token_session import group_key_aad, lock_path, open_token_session, session_path
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport
from diagnos.transport.service_token import DiagnosToken
from diagnos.transport.token import ServiceAccountToken


class _Vault:
    """🇺🇸 `transport.post` for the two token routes, recording what was asked. 🇧🇷 `transport.post` das duas rotas."""

    def __init__(self, token: DiagnosToken, **answer: Any) -> None:
        """🇺🇸 Answers built for `token`. 🇧🇷 Respostas montadas para `token`."""
        self.token = token
        self.answer = answer
        self.posts: list[tuple[str, bool]] = []

    def post(self, path: str, *, json: Any | None = None, signed: bool = True) -> Any:
        """🇺🇸 Session → sealed material; lock → `{revoked: true}`. 🇧🇷 Sessão → material selado; lock → revogado."""
        assert json is None, "the session route takes no body · a rota de sessão não tem corpo"
        self.posts.append((path, signed))
        return session_answer(self.token, **self.answer) if path.endswith("/session") else {"revoked": True}


def test_one_unsigned_post_opens_the_session_and_every_group_key() -> None:
    """🇺🇸 No session HMAC yet (`signed=False`); the keyring holds the sealed session and the group's 32 bytes.

    🇧🇷 Ainda sem HMAC de sessão (`signed=False`); o keyring tem a sessão selada e os 32 bytes do grupo.
    """
    token = parsed("wsSes")
    vault = _Vault(token)
    keyring = open_token_session(vault, token, token.keypair())  # type: ignore[arg-type]
    assert vault.posts == [(session_path("wsSes"), False)]
    assert session_path("wsSes") == "/api/external/v1/workspaces/wsSes/session"
    assert (keyring.session.session_id, keyring.session.expires_at, keyring.enrollment_id) == ("ses_1", 4e9, "ses_1")
    assert bytes(keyring.group_key("sg_1").reveal()) == GROUP_KEY
    assert len(keyring.session.sign_key) == len(keyring.session.enc_key) == 32


def test_a_seal_bound_to_another_key_does_not_open() -> None:
    """🇺🇸 Same recipient keys, AAD of another `key_id`: AES-GCM refuses — a swapped seal never opens.

    🇧🇷 Mesmas chaves de destinatário, AAD de outro `key_id`: o AES-GCM recusa — selo trocado nunca abre.
    """
    token = parsed()
    with pytest.raises(CryptoError):
        open_token_session(_Vault(token, aad_key_id="svc_" + "0" * 32), token, token.keypair())  # type: ignore[arg-type]


def test_a_session_id_beside_the_seal_must_agree_with_the_one_inside() -> None:
    """🇺🇸 The authenticated id wins; a disagreeing copy is a protocol error. 🇧🇷 Divergir do id selado é erro."""
    token = parsed()
    with pytest.raises(ProtocolError, match="disagrees"):
        open_token_session(_Vault(token, session_id="ses_other"), token, token.keypair())  # type: ignore[arg-type]


def test_a_group_key_of_the_wrong_size_is_refused() -> None:
    """🇺🇸 A group key is 32 bytes; anything else is a protocol mismatch. 🇧🇷 Uma chave de grupo tem 32 bytes."""
    token = parsed()
    vault = _Vault(token)
    answer = session_answer(token)
    aad = group_key_aad(token.workspace_id, token.key_id, "sg_2")
    answer["sealed_group_keys"]["sg_2"] = seal_to(token, b"short", aad)
    vault.post = lambda path, **kwargs: answer  # type: ignore[method-assign]
    with pytest.raises(CryptoError, match="expected 32"):
        open_token_session(vault, token, token.keypair())  # type: ignore[arg-type]


def test_the_manager_opens_with_the_token_locks_on_its_route_and_reopens_without_a_human() -> None:
    """🇺🇸 `unlock` → session route; `lock` → the token's lock route; `reopen` → a fresh session, no prompt.

    🇧🇷 `unlock` → rota de sessão; `lock` → a rota de lock do token; `reopen` → sessão nova, sem prompt.
    """
    token = parsed("wsMgr")
    vault = _Vault(token)
    prompts: list[Any] = []
    manager = SessionManager(Settings(token=token), token, vault, on_prompt=prompts.append)  # type: ignore[arg-type]
    first = manager.unlock()
    assert manager.reopen() is True
    assert manager.keyring is not first and first.session.sign_key.is_wiped
    manager.lock()
    assert manager.session_keys() is None and token.is_wiped is False
    assert [path for path, _ in vault.posts] == [session_path("wsMgr")] * 2 + [lock_path("wsMgr")]
    assert lock_path("wsMgr") == "/api/external/v1/workspaces/wsMgr/session/lock"
    assert vault.posts[-1] == (lock_path("wsMgr"), True)
    assert prompts == []


def test_a_failed_open_wipes_the_pair_and_the_legacy_token_cannot_reopen() -> None:
    """🇺🇸 The copy of the seal pair dies with a failed open; a legacy session needs a human, so no reopen.

    🇧🇷 A cópia do par de selo morre com uma abertura que falhou; uma sessão legada precisa de pessoa, sem reabrir.
    """
    token = parsed()
    manager = SessionManager(Settings(token=token), token, _Vault(token, session_id="x"))  # type: ignore[arg-type]
    with pytest.raises(ProtocolError):
        manager.unlock()
    assert manager.keypair is None
    legacy = ServiceAccountToken.parse(legacy_token())
    assert SessionManager(Settings(api_token=legacy.raw), legacy, _Vault(token)).reopen() is False  # type: ignore[arg-type]


def _transport(handler: Any, reopen: Any) -> VaultTransport:
    """🇺🇸 A real transport over `handler`, with `reopen` as the lost-session hook. 🇧🇷 Um transporte real."""
    token = parsed()
    return VaultTransport(
        Settings(token=token, vault_url="https://vault.test"),
        token,
        session_keys=lambda: None,
        on_session_lost=reopen,
        client=httpx.Client(base_url="https://vault.test", transport=httpx.MockTransport(handler)),
        sleep=lambda seconds: None,
    )


def _lost() -> httpx.Response:
    """🇺🇸 The vault no longer knows the session. 🇧🇷 O cofre não conhece mais a sessão."""
    return httpx.Response(401, json={"success": False, "errors": [{"code": "SessionNotFound", "message": "gone"}]})


@pytest.mark.parametrize(("reopens", "calls"), [(True, 2), (False, 1)])
def test_a_lost_session_is_reopened_and_retried_once(reopens: bool, calls: int) -> None:
    """🇺🇸 `SessionNotFound` → reopen → one retry; a hook that cannot reopen lets the error through.

    🇧🇷 `SessionNotFound` → reabre → uma retentativa; um gancho que não consegue reabrir deixa o erro passar.
    """
    attempts: list[int] = []
    hooks: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return httpx.Response(200, json={"result": 1_760_000_000_000})
        attempts.append(1)
        return _lost()

    with pytest.raises(AuthenticationError, match="SessionNotFound"):
        _transport(handler, lambda: hooks.append(1) or reopens).get("/api/external/v1/x", signed=False)
    assert len(attempts) == 1
    keys = SessionKeys("s", SecretBox.random(32), SecretBox.random(32), 4_000_000_000)
    attempts.clear()
    transport = _transport(handler, lambda: hooks.append(1) or reopens)
    transport._session_keys = lambda: keys  # noqa: SLF001
    with pytest.raises(AuthenticationError):
        transport.get("/api/external/v1/x")
    assert len(attempts) == calls
