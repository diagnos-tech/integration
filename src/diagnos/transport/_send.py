"""`_SendMixin`: build one signed request and send it, and opportunistically open `random_seed`.

`VaultTransport.request` calls `_send_once` once per loop iteration and
`_maybe_deliver_seed` after every response; neither needs the retry loop
itself, so pulling them out here is what keeps `http.py` down to the loop
and the public `get`/`post`/`put`/`request` surface. Its methods take
`self: _SendHost`, a structural `Protocol` naming just the four attributes
they touch — not `self: VaultTransport` itself, because mypy requires an
explicit self-type to be a *supertype* of the defining class, and
`VaultTransport` (which inherits this mixin) is the other way round: a
subtype of it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Protocol

import httpx

from diagnos.crypto.secure import SecretBox
from diagnos.errors import SessionExpiredError
from diagnos.session.keyring import SessionKeys

from .seed import open_random_seed
from .signing import new_nonce, signature_headers
from .timesync import ClockSync

logger = logging.getLogger("diagnos")


class _SendHost(Protocol):
    """What `_SendMixin` needs from `VaultTransport` — see the module docstring for why this is a `Protocol`."""

    _client: httpx.Client
    _session_keys: Callable[[], SessionKeys | None]
    _clock: ClockSync
    _on_seed: Callable[[SecretBox], None] | None


class _SendMixin:
    """The per-request half of `VaultTransport`: sign-and-send, plus opportunistic seed delivery."""

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
        """Build one request (signing it if asked) and send it — no retry logic here."""
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
        """Open the envelope's `random_seed` and hand it to `on_seed` as a `SecretBox`; never fail the call.

        A seed that is absent or does not open (a body that is not JSON,
        a stale `enc_key` mid-rotation) is a lost contribution to future
        entropy, not a reason to fail a response the vault otherwise answered
        correctly — the SDK still has the OS RNG on its own.
        """
        if self._on_seed is None:
            return
        keys = self._session_keys()
        if keys is None:
            return
        try:
            body = response.json()
        except ValueError:
            return
        envelope = body.get("random_seed") if isinstance(body, dict) else None
        if not isinstance(envelope, dict):
            return
        try:
            seed = open_random_seed(keys.enc_key, keys.session_id, envelope)
        except Exception:
            logger.debug("random_seed did not open", exc_info=True)
            return
        self._on_seed(seed)
