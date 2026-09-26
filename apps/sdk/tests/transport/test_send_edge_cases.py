"""🇺🇸 `transport/_send.py`: the fail-closed signed path, and every way `random_seed` delivery can quietly do nothing.

`_maybe_deliver_seed` promises in its own docstring to "never fail the
call" — every test here proves one specific way it can fail to *deliver* a
seed (no callback, no session, a non-JSON body, no `random_seed` field, a
field that does not open) without ever raising out of `VaultTransport.request`.
The one exception, `_send_once`, is the opposite promise: signing without a
live session must fail loudly (`SessionExpiredError`), not silently sign
with nothing.

🇧🇷 `transport/_send.py`: o caminho assinado que falha fechado, e toda forma
de a entrega de `random_seed` silenciosamente não fazer nada.

`_maybe_deliver_seed` promete na própria docstring "nunca falhar a
chamada" — cada teste aqui prova um jeito específico de ela deixar de
*entregar* uma semente (sem callback, sem sessão, corpo que não é JSON, sem
campo `random_seed`, campo que não abre) sem nunca lançar para fora de
`VaultTransport.request`. A única exceção, `_send_once`, é a promessa
oposta: assinar sem sessão viva precisa falhar alto (`SessionExpiredError`),
não assinar em silêncio com nada.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable

import httpx
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnos.crypto.encoding import b64url_encode
from diagnos.crypto.secure import SecretBox
from diagnos.errors import SessionExpiredError, VaultError
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


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    """🇺🇸 An `httpx.Client` wired to a `MockTransport` instead of a socket.

    🇧🇷 Um `httpx.Client` ligado a um `MockTransport` em vez de um socket.
    """
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://vault.example.test")


def _time_response(request: httpx.Request) -> httpx.Response:
    """🇺🇸 The raw (unenveloped) shape `GET /time` answers with. 🇧🇷 A forma crua de `GET /time`."""
    assert request.method == "GET"
    return httpx.Response(200, json={"result": 1_700_000_000_000})


def _fresh_session_keys() -> SessionKeys:
    """🇺🇸 A session that will not expire mid-test. 🇧🇷 Uma sessão que não expira no meio do teste."""
    return SessionKeys(
        session_id="sess_1",
        sign_key=SecretBox.from_bytes(bytearray(secrets.token_bytes(32))),
        enc_key=SecretBox.from_bytes(bytearray(secrets.token_bytes(32))),
        expires_at=9_999_999_999,
    )


def _make_transport(
    *,
    handler: Callable[[httpx.Request], httpx.Response],
    session_keys: Callable[[], SessionKeys | None],
    on_seed: Callable[[SecretBox], None] | None,
) -> VaultTransport:
    """🇺🇸 A `VaultTransport` whose only moving parts are `session_keys`/`on_seed`.

    🇧🇷 Um `VaultTransport` cujas únicas peças móveis são `session_keys`/`on_seed`.
    """
    settings = Settings(api_token="apikey-test", vault_url="https://vault.example.test")  # noqa: S106
    return VaultTransport(
        settings,
        _TOKEN,
        session_keys=session_keys,
        on_seed=on_seed,
        client=_client(handler),
        storage_client=_client(lambda r: httpx.Response(200)),
        sleep=lambda seconds: None,
    )


# -- _send_once: signing without a live session fails closed -------------------


def test_a_signed_call_with_no_session_keys_raises_session_expired_before_any_request() -> None:
    """🇺🇸 `session_keys()` returning `None` on a signed call raises `SessionExpiredError`, not a bare `401`.

    🇧🇷 `session_keys()` devolvendo `None` numa chamada assinada lança `SessionExpiredError`, não um `401` cru.
    """
    called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        raise AssertionError("no request should ever be sent without a live session")

    transport = _make_transport(handler=handler, session_keys=lambda: None, on_seed=None)

    with pytest.raises(SessionExpiredError):
        transport.get(_WIDGET_PATH, signed=True)

    assert called["n"] == 0


# -- _maybe_deliver_seed: every way delivery quietly does nothing -------------


def _envelope_with(body: object) -> Callable[[httpx.Request], httpx.Response]:
    """🇺🇸 A handler answering `/time` normally and every other path with `body` as JSON.

    🇧🇷 Um handler que responde `/time` normal e todo outro path com `body` como JSON.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return _time_response(request)
        return httpx.Response(200, json=body)

    return handler


def test_seed_delivery_is_skipped_with_no_on_seed_callback() -> None:
    """🇺🇸 Without `on_seed`, a `random_seed` in the envelope is never even inspected.

    🇧🇷 Sem `on_seed`, um `random_seed` no envelope nunca é sequer inspecionado.
    """
    keys = _fresh_session_keys()
    handler = _envelope_with({"success": True, "result": None, "random_seed": {"nonce": "x", "ciphertext": "y"}})
    transport = _make_transport(handler=handler, session_keys=lambda: keys, on_seed=None)

    result = transport.get(_WIDGET_PATH)  # 🇺🇸/🇧🇷 must not raise · não pode lançar

    assert result is None


def test_seed_delivery_is_skipped_when_the_session_has_no_keys() -> None:
    """🇺🇸 A session that has keys to sign the request but none left by the time the response arrives delivers nothing.

    `session_keys()` is asked twice per signed call — once by `_send_once` to
    sign, once again by `_maybe_deliver_seed` afterward — so a session that
    lapses in between (a tiny, real race) must not raise a second time; it
    just skips delivery.

    🇧🇷 Uma sessão com chaves para assinar a requisição mas nenhuma sobrando
    quando a resposta chega não entrega nada.

    `session_keys()` é perguntado duas vezes por chamada assinada — uma por
    `_send_once` para assinar, outra por `_maybe_deliver_seed` depois — então
    uma sessão que vence no meio (uma corrida pequena, real) não pode lançar
    uma segunda vez; ela só pula a entrega.
    """
    keys = _fresh_session_keys()
    calls = {"n": 0}

    def session_keys() -> SessionKeys | None:
        calls["n"] += 1
        return keys if calls["n"] == 1 else None

    handler = _envelope_with({"success": True, "result": None, "random_seed": {"nonce": "x", "ciphertext": "y"}})
    received: list[SecretBox] = []
    transport = _make_transport(handler=handler, session_keys=session_keys, on_seed=received.append)

    result = transport.get(_WIDGET_PATH, signed=True)

    assert result is None
    assert received == []
    assert calls["n"] == 2


def test_seed_delivery_is_skipped_when_the_response_body_is_not_json() -> None:
    """🇺🇸 A non-JSON body (a proxy error page) never reaches the `random_seed` parsing at all.

    🇧🇷 Um corpo que não é JSON (uma página de erro de proxy) nunca chega ao parse de `random_seed`.
    """
    keys = _fresh_session_keys()
    received: list[SecretBox] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/time":
            return _time_response(request)
        return httpx.Response(200, content=b"<html>not json</html>")

    transport = _make_transport(handler=handler, session_keys=lambda: keys, on_seed=received.append)

    with pytest.raises(VaultError, match="InvalidResponse"):
        transport.get(_WIDGET_PATH)

    assert received == []  # 🇺🇸/🇧🇷 seed delivery never even attempted · entrega de seed nunca tentada


@pytest.mark.parametrize(
    "body",
    [
        {"success": True, "result": None},
        {"success": True, "result": None, "random_seed": None},
        {"success": True, "result": None, "random_seed": "not-a-dict"},
        {"success": True, "result": None, "random_seed": []},
    ],
    ids=["absent", "null", "string", "list"],
)
def test_seed_delivery_is_skipped_when_random_seed_is_missing_or_not_an_object(body: object) -> None:
    """🇺🇸 A missing, `null`, or non-object `random_seed` is treated as "nothing to mix in".

    🇧🇷 Um `random_seed` ausente, `null` ou que não é objeto é tratado como "nada para misturar".
    """
    keys = _fresh_session_keys()
    received: list[SecretBox] = []
    transport = _make_transport(handler=_envelope_with(body), session_keys=lambda: keys, on_seed=received.append)

    result = transport.get(_WIDGET_PATH)

    assert result is None
    assert received == []


def test_seed_delivery_swallows_a_random_seed_that_does_not_open() -> None:
    """🇺🇸 A `random_seed` sealed under a different `enc_key` (or otherwise garbled) is logged, not raised.

    🇧🇷 Um `random_seed` selado sob outro `enc_key` (ou de outra forma corrompido) é logado, não lançado.
    """
    keys = _fresh_session_keys()
    received: list[SecretBox] = []
    garbled = {"nonce": "AAAAAAAAAAAAAAAA", "ciphertext": "not-really-ciphertext-at-all"}
    handler = _envelope_with({"success": True, "result": {"ok": True}, "random_seed": garbled})
    transport = _make_transport(handler=handler, session_keys=lambda: keys, on_seed=received.append)

    result = transport.get(_WIDGET_PATH)  # 🇺🇸/🇧🇷 must not raise · não pode lançar

    assert result == {"ok": True}
    assert received == []


def test_seed_delivery_swallows_a_correctly_opened_but_wrong_length_seed() -> None:
    """🇺🇸 A `random_seed` that opens cleanly but decodes to the wrong byte count is discarded, not raised.

    A valid AEAD tag only proves the bytes were not tampered with in
    transit — it says nothing about whether the vault is speaking the exact
    version of the protocol this SDK expects. `PROTOCOL.md §4` fixes the
    seed at 32 bytes, so any other length is treated the same as a seed that
    failed to open at all.

    🇧🇷 Um `random_seed` que abre limpo mas decodifica para uma contagem de
    bytes errada é descartado, não lançado.

    Uma tag AEAD válida só prova que os bytes não foram adulterados em
    trânsito — não diz nada sobre o cofre falar exatamente a versão do
    protocolo que este SDK espera. `PROTOCOL.md §4` fixa a semente em 32
    bytes, então qualquer outro tamanho é tratado igual a uma semente que
    não abriu de jeito nenhum.
    """
    enc_key = secrets.token_bytes(32)
    session_id = "sess_1"
    wrong_size_seed = secrets.token_bytes(16)  # 🇺🇸/🇧🇷 16, not the required 32 bytes
    nonce = secrets.token_bytes(12)
    plaintext = json.dumps({"seed": b64url_encode(wrong_size_seed)}).encode("utf-8")
    ciphertext = AESGCM(enc_key).encrypt(nonce, plaintext, session_id.encode("utf-8"))
    envelope = {"nonce": b64url_encode(nonce), "ciphertext": b64url_encode(ciphertext)}

    keys = SessionKeys(
        session_id=session_id,
        sign_key=SecretBox.from_bytes(bytearray(secrets.token_bytes(32))),
        enc_key=SecretBox.from_bytes(bytearray(enc_key)),
        expires_at=9_999_999_999,
    )
    received: list[SecretBox] = []
    handler = _envelope_with({"success": True, "result": {"ok": True}, "random_seed": envelope})
    transport = _make_transport(handler=handler, session_keys=lambda: keys, on_seed=received.append)

    result = transport.get(_WIDGET_PATH)  # 🇺🇸/🇧🇷 must not raise · não pode lançar

    assert result == {"ok": True}
    assert received == []
