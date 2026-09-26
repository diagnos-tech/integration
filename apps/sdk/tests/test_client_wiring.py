"""🇺🇸 `Diagnos`: what it wires together when a caller does *not* pass `transport`/`session` at all.

Split out of `test_client.py` (its ~400-line convention) — this file is
specifically about the construction branch `Diagnos.__init__` takes when
`transport`/`session` stay `None`: a real `VaultTransport`/`SessionManager`
get built, `on_prompt` falls back to `session.manager.default_prompt`, and
`auto_unseal`/`settings.openbao_addr` decide whether a store is attached.
None of this makes a network call at construction time, so it is safe to
build against the default (production) `vault_url`.

🇧🇷 `Diagnos`: o que ele conecta quando quem chama *não* passa
`transport`/`session` nenhum.

Separado de `test_client.py` (a convenção de ~400 linhas do pacote) — este
arquivo é especificamente sobre o ramo de construção que `Diagnos.__init__`
segue quando `transport`/`session` ficam `None`: um `VaultTransport`/
`SessionManager` de verdade são construídos, `on_prompt` cai para
`session.manager.default_prompt`, e `auto_unseal`/`settings.openbao_addr`
decidem se um store é conectado. Nada disso faz chamada de rede na
construção, então é seguro construir contra o `vault_url` padrão (produção).
"""

from __future__ import annotations

import json

import httpx
import pytest
from diagnos.client import Diagnos
from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.secure import SecretBox
from diagnos.session.keyring import Keyring, SessionKeys
from diagnos.session.manager import SessionManager, default_prompt
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport

_VALID_PAYLOAD = {
    "sub": "key_123",
    "account_id": "acc_1",
    "workspace_id": "ws_1",
    "name": "svc@ws_1.diagnos.health",
}


def _make_apikey() -> str:
    """🇺🇸 A syntactically valid `apikey-<jwt>` for `ws_1`/`acc_1`, unsigned.

    🇧🇷 Um `apikey-<jwt>` sintaticamente válido para `ws_1`/`acc_1`, sem assinatura.
    """
    header_b64 = b64url_encode(json.dumps({"alg": "EdDSA", "typ": "JWT"}).encode("utf-8"))
    payload_b64 = b64url_encode(json.dumps(_VALID_PAYLOAD).encode("utf-8"))
    signature_b64 = b64url_encode(b"fake-signature")
    return f"apikey-{header_b64}.{payload_b64}.{signature_b64}"


def _settings(**overrides: object) -> Settings:
    """🇺🇸 `Settings` with a valid token for `ws_1`/`acc_1`, everything else overridable.

    🇧🇷 `Settings` com um token válido para `ws_1`/`acc_1`, o resto sobrescrevível.
    """
    return Settings(api_token=_make_apikey(), **overrides)  # type: ignore[arg-type]


class _FakeTransport:
    """🇺🇸 A `transport=` stand-in for tests that only need `close()` to be harmless.

    🇧🇷 Um substituto de `transport=` para testes que só precisam de um `close()` inofensivo.
    """

    def close(self) -> None:
        """🇺🇸 Does nothing. 🇧🇷 Não faz nada."""


def test_current_session_keys_callback_reaches_the_live_session() -> None:
    """🇺🇸 The bound `_current_session_keys` callback wired into a real `VaultTransport` signs from the session.

    Every other test in this file either checks types only or never sends a
    signed request, so `Diagnos._current_session_keys` — the private
    callback `VaultTransport(session_keys=...)` actually polls — never runs.
    This test builds the real default transport (`transport=None`) and
    swaps only its inner `httpx.Client` for a `MockTransport`, so a signed
    `GET` exercises the callback exactly as production does.

    🇧🇷 O callback `_current_session_keys`, ligado a um `VaultTransport` de
    verdade, assina a partir da sessão.

    Todo outro teste deste arquivo ou só confere tipos ou nunca manda uma
    requisição assinada, então `Diagnos._current_session_keys` — o callback
    privado que `VaultTransport(session_keys=...)` de fato consulta — nunca
    roda. Este teste constrói o transporte padrão de verdade
    (`transport=None`) e troca só o `httpx.Client` interno dele por um
    `MockTransport`, para um `GET` assinado exercitar o callback exatamente
    como em produção.
    """
    keyring = Keyring(
        enrollment_id="enr_1",
        session=SessionKeys(
            session_id="sess_1",
            sign_key=SecretBox.random(32),
            enc_key=SecretBox.random(32),
            expires_at=9_999_999_999,
        ),
        group_keys={},
    )

    class _UnlockedSession:
        def session_keys(self) -> SessionKeys:
            return keyring.session

    vault = Diagnos(settings=_settings(), session=_UnlockedSession())  # type: ignore[arg-type]
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return httpx.Response(200, json={"result": 1_700_000_000_000})
        seen_headers.update(request.headers)
        return httpx.Response(
            200,
            json={"success": True, "status": "success", "status_code": 200, "result": {"ok": True}, "docs": "d"},
        )

    vault._transport._client = httpx.Client(  # noqa: SLF001 — swapping the real client for a mock one
        transport=httpx.MockTransport(handler), base_url="https://vault.example.test"
    )

    try:
        result = vault._transport.get(f"/api/external/v1/workspaces/{vault.workspace_id}/widgets")  # noqa: SLF001
    finally:
        vault.close()

    assert result == {"ok": True}
    # 🇺🇸/🇧🇷 signed with the fake session's own key · assinado com a chave da sessão falsa
    assert "x-signature-hmac" in seen_headers


def test_default_wiring_builds_a_real_transport_and_session_manager() -> None:
    """🇺🇸 Without `transport`/`session`, `Diagnos` builds a real `VaultTransport`/`SessionManager`.

    🇧🇷 Sem `transport`/`session`, `Diagnos` constrói um `VaultTransport`/`SessionManager` de verdade.
    """
    vault = Diagnos(settings=_settings())
    try:
        assert isinstance(vault._transport, VaultTransport)  # noqa: SLF001
        assert isinstance(vault._session, SessionManager)  # noqa: SLF001
    finally:
        vault.close()


def test_on_prompt_defaults_to_the_manager_default_prompt() -> None:
    """🇺🇸 With no `on_prompt`, the built `SessionManager` gets `default_prompt`.

    🇧🇷 Sem `on_prompt`, o `SessionManager` construído recebe `default_prompt`.
    """
    vault = Diagnos(settings=_settings(), transport=_FakeTransport())  # type: ignore[arg-type]
    assert vault._session._on_prompt is default_prompt  # noqa: SLF001


def test_on_prompt_uses_the_callback_given() -> None:
    """🇺🇸 An explicit `on_prompt` reaches the built `SessionManager` unchanged.

    🇧🇷 Um `on_prompt` explícito chega ao `SessionManager` construído sem mudanças.
    """
    prompts: list[object] = []
    vault = Diagnos(settings=_settings(), transport=_FakeTransport(), on_prompt=prompts.append)  # type: ignore[arg-type]
    # 🇺🇸/🇧🇷 `==`, not `is`: two accesses of a bound method (`list.append`) are equal but not the same object.
    assert vault._session._on_prompt == prompts.append  # noqa: SLF001


def test_auto_unseal_defaults_from_openbao_addr_and_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 A store is built exactly when `auto_unseal` (or `openbao_addr`, by default) says so — never otherwise.

    `OpenBaoStore` is replaced with a recording double so this exercises only
    `Diagnos`'s own branch (`auto_unseal if auto_unseal is not None else
    settings.openbao_addr is not None`), not `hvac`'s tolerance for a
    partial configuration.

    🇧🇷 Um store é construído exatamente quando `auto_unseal` (ou, por padrão,
    `openbao_addr`) diz que sim — nunca do contrário.

    `OpenBaoStore` é substituído por um duplo que grava, para isto exercitar
    só o próprio ramo do `Diagnos` (`auto_unseal if auto_unseal is not None
    else settings.openbao_addr is not None`), não a tolerância do `hvac` a
    uma configuração parcial.
    """
    created: list[dict[str, str]] = []

    class _DummyStore:
        def __init__(self, settings: Settings, *, workspace_id: str, account_id: str) -> None:
            created.append({"workspace_id": workspace_id, "account_id": account_id})

    monkeypatch.setattr("diagnos.client.OpenBaoStore", _DummyStore)

    # 🇺🇸/🇧🇷 no `openbao_addr`, `auto_unseal` left to its default → no store.
    no_addr = Diagnos(settings=_settings(), transport=_FakeTransport())  # type: ignore[arg-type]
    assert no_addr._session._store is None  # noqa: SLF001
    assert created == []

    # 🇺🇸/🇧🇷 `openbao_addr` set → a store is built automatically.
    with_addr = Diagnos(
        settings=_settings(openbao_addr="https://bao.example.test"),
        transport=_FakeTransport(),  # type: ignore[arg-type]
    )
    assert isinstance(with_addr._session._store, _DummyStore)  # noqa: SLF001
    assert created == [{"workspace_id": "ws_1", "account_id": "acc_1"}]
    created.clear()

    # 🇺🇸/🇧🇷 `openbao_addr` set, but `auto_unseal=False` explicitly opts out.
    opted_out = Diagnos(
        settings=_settings(openbao_addr="https://bao.example.test"),
        transport=_FakeTransport(),  # type: ignore[arg-type]
        auto_unseal=False,
    )
    assert opted_out._session._store is None  # noqa: SLF001
    assert created == []

    # 🇺🇸/🇧🇷 no `openbao_addr`, but `auto_unseal=True` forces a store anyway.
    forced = Diagnos(settings=_settings(), transport=_FakeTransport(), auto_unseal=True)  # type: ignore[arg-type]
    assert isinstance(forced._session._store, _DummyStore)  # noqa: SLF001
