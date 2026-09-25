"""🇺🇸 `_SendMixin`: build one signed request and send it, and opportunistically open `X-Session-Seed`.

`VaultTransport.request` calls `_send_once` once per loop iteration and
`_maybe_deliver_seed` after every response; neither needs the retry loop
itself, so pulling them out here is what keeps `http.py` down to the loop
and the public `get`/`post`/`put`/`request` surface. Its methods take
`self: _SendHost`, a structural `Protocol` naming just the four attributes
they touch — not `self: VaultTransport` itself, because mypy requires an
explicit self-type to be a *supertype* of the defining class, and
`VaultTransport` (which inherits this mixin) is the other way round: a
subtype of it.

🇧🇷 `_SendMixin`: monta uma requisição assinada e envia, e abre `X-Session-Seed` de forma oportunista.

`VaultTransport.request` chama `_send_once` uma vez por volta do laço e
`_maybe_deliver_seed` depois de toda resposta; nenhum dos dois precisa do
próprio laço de retentativa, então tirá-los daqui é o que mantém `http.py`
restrito ao laço e à superfície pública `get`/`post`/`put`/`request`. Seus
métodos recebem `self: _SendHost`, um `Protocol` estrutural que só nomeia os
quatro atributos que eles tocam — não `self: VaultTransport` em si, porque
o mypy exige que um self-type explícito seja um *supertipo* da classe que o
define, e `VaultTransport` (que herda este mixin) é o contrário disso: um
subtipo dele.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Protocol

import httpx

from diagnos.crypto.secure import SecretBox
from diagnos.errors import SessionExpiredError
from diagnos.session.keyring import SessionKeys

from .seed import open_session_seed
from .signing import new_nonce, signature_headers
from .timesync import ClockSync

logger = logging.getLogger("diagnos")


class _SendHost(Protocol):
    """🇺🇸 What `_SendMixin` needs from `VaultTransport` — see the module docstring for why this is a `Protocol`.

    🇧🇷 O que `_SendMixin` precisa de `VaultTransport` — ver a docstring do módulo para o porquê de `Protocol`.
    """

    _client: httpx.Client
    _session_keys: Callable[[], SessionKeys | None]
    _clock: ClockSync
    _on_seed: Callable[[SecretBox], None] | None


class _SendMixin:
    """🇺🇸 The per-request half of `VaultTransport`: sign-and-send, plus opportunistic seed delivery.

    🇧🇷 A metade por-requisição de `VaultTransport`: assinar-e-enviar, mais entrega oportunista de seed.
    """

    def _send_once(
        self: _SendHost,
        method: str,
        path: str,
        *,
        query: Mapping[str, str | int | bool] | None,
        body: bytes,
        headers: Mapping[str, str],
        signed: bool,
    ) -> httpx.Response:
        """🇺🇸 Build one request (signing it if asked) and send it — no retry logic here.

        🇧🇷 Monta uma requisição (assinando se pedido) e envia — sem lógica de retentativa aqui.
        """
        request = self._client.build_request(method, path, params=query, content=body, headers=dict(headers))
        if signed:
            keys = self._session_keys()
            if keys is None:
                raise SessionExpiredError(
                    "🇺🇸 no session keys available; enroll (or restore from OpenBao) before "
                    "making signed calls. "
                    "🇧🇷 nenhuma chave de sessão disponível; faça enrollment (ou restaure do "
                    "OpenBao) antes de chamadas assinadas."
                )
            if not self._clock.is_synced:
                self._clock.sync(self._client)
            sig_headers = signature_headers(
                keys.sign_key,
                method=method,
                url=request.url,
                body=body,
                timestamp=self._clock.now_seconds(),
                nonce=new_nonce(),
            )
            request.headers.update(sig_headers)
        return self._client.send(request)

    def _maybe_deliver_seed(self: _SendHost, response: httpx.Response) -> None:
        """🇺🇸 Open `X-Session-Seed` and hand it to `on_seed` as a `SecretBox`; never let this fail the call.

        A seed that does not open (stale `enc_key` mid-rotation, a proxy that
        stripped the header) is a lost contribution to future entropy, not a
        reason to fail a response the vault otherwise answered correctly —
        the SDK still has the OS RNG on its own.

        🇧🇷 Abre `X-Session-Seed` e entrega a `on_seed` como `SecretBox`; nunca deixa isso derrubar a chamada.

        Uma semente que não abre (`enc_key` velho no meio de uma rotação, um
        proxy que removeu o header) é uma contribuição perdida para entropia
        futura, não motivo para falhar uma resposta que o cofre respondeu
        certo — o SDK ainda tem o RNG do SO por conta própria.
        """
        header_value = response.headers.get("X-Session-Seed")
        if header_value is None or self._on_seed is None:
            return
        keys = self._session_keys()
        if keys is None:
            return
        try:
            seed = open_session_seed(keys.enc_key, keys.session_id, header_value)
        except Exception:
            logger.debug("X-Session-Seed did not open", exc_info=True)
            return
        self._on_seed(seed)
