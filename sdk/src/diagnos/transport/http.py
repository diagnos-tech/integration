"""🇺🇸 `VaultTransport` — the one place that speaks HTTP to the vault.

Everything above this module (resources, the CLI) calls `request`/`get`/
`post`/`put` and never touches `httpx` directly, so every retry rule, every
header, every envelope in `docs/PROTOCOL.md` is enforced exactly once. Two
transports live inside it: a signed `httpx.Client` for `/api/external/v1`
(and the unsigned `/time`), and a bare `httpx.Client` with no base URL and no
`Authorization` for the R2 object storage the vault only ever hands out
presigned URLs to. The `429`/`5xx` backoff math lives in `_retry.py`, and the
bare R2 `PUT`/`GET`s live in `storage.py` — this module keeps only what
needs signing, session state, or the retry loop itself.

🇧🇷 `VaultTransport` — o único lugar que fala HTTP com o cofre.

Tudo acima deste módulo (recursos, CLI) chama `request`/`get`/`post`/`put` e
nunca toca `httpx` direto, então toda regra de retentativa, todo header, todo
envelope de `docs/PROTOCOL.md` é aplicado uma única vez. Dois transportes
vivem aqui dentro: um `httpx.Client` assinado para `/api/external/v1` (e o
`/time` sem assinatura), e um `httpx.Client` nu, sem base URL nem
`Authorization`, para o armazenamento de objetos do R2, para o qual o cofre
só entrega URLs pré-assinadas. A matemática de backoff de `429`/`5xx` vive em
`_retry.py`, e os `PUT`/`GET`s nus do R2 vivem em `storage.py` — este módulo
guarda só o que precisa de assinatura, estado de sessão, ou o próprio laço de
retentativa.
"""

from __future__ import annotations

import json as json_module
import time
from collections.abc import Callable, Mapping
from types import TracebackType
from typing import Any

import httpx

from diagnos.crypto.secure import SecretBox
from diagnos.errors import AuthenticationError, ConflictError
from diagnos.session.keyring import SessionKeys

from ._retry import MAX_RATE_LIMIT_RETRIES, SERVER_ERROR_BACKOFF_SECONDS, rate_limit_wait_seconds
from ._send import _SendMixin
from .config import Settings
from .envelope import unwrap_result
from .storage import _StorageMixin
from .timesync import ClockSync
from .token import ServiceAccountToken


def _encode_json_body(payload: Any | None) -> bytes:
    """🇺🇸 Same separators the vault expects, and the exact bytes we then sign.

    `separators=(",", ":")` drops the spaces `json.dumps` adds by default;
    signing has to run over the *literal* bytes sent on the wire, so any
    difference between what is signed and what is serialized here would be a
    self-inflicted `401`.

    🇧🇷 Os mesmos separadores que o cofre espera, e os bytes exatos que assinamos.

    `separators=(",", ":")` tira os espaços que `json.dumps` adiciona por
    padrão; a assinatura precisa rodar sobre os bytes *literais* enviados no
    fio, então qualquer diferença entre o que é assinado e o que é
    serializado aqui seria um `401` autoinfligido.
    """
    if payload is None:
        return b""
    return json_module.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class VaultTransport(_StorageMixin, _SendMixin):
    """🇺🇸 Signs, sends, retries and unwraps every call to the vault's API.

    `upload_bytes`/`download_bytes`/`download_stream` — the R2 side, which
    needs none of that — come from `_StorageMixin` (`storage.py`); building,
    signing and sending one request, plus opportunistic seed delivery, come
    from `_SendMixin` (`_send.py`).

    🇧🇷 Assina, envia, retenta e desembrulha toda chamada à API do cofre.

    `upload_bytes`/`download_bytes`/`download_stream` — o lado R2, que não
    precisa de nada disso — vêm de `_StorageMixin` (`storage.py`); montar,
    assinar e enviar uma requisição, mais a entrega oportunista de seed, vêm
    de `_SendMixin` (`_send.py`).
    """

    def __init__(
        self,
        settings: Settings,
        token: ServiceAccountToken,
        *,
        session_keys: Callable[[], SessionKeys | None],
        on_seed: Callable[[SecretBox], None] | None = None,
        client: httpx.Client | None = None,
        storage_client: httpx.Client | None = None,
        clock: ClockSync | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """🇺🇸 Wrap `settings`/`token` with the callbacks and clients a live session needs.

        🇧🇷 Envolve `settings`/`token` com os callbacks e clients de que uma sessão viva precisa.
        """
        # 🇺🇸 `session_keys` is a callback, not a value, because the keys can
        # rotate (re-enrollment, seed-derived refresh) after this transport is
        # built; the transport must always ask for the current ones.
        # 🇧🇷 `session_keys` é um callback, não um valor, porque as chaves podem
        # rotacionar (novo enrollment, refresh via semente) depois do
        # transporte pronto; ele sempre precisa pedir as atuais.
        self._settings = settings
        self._token = token
        self._session_keys = session_keys
        self._on_seed = on_seed
        self._client = (
            client
            if client is not None
            else httpx.Client(base_url=settings.vault_url, timeout=settings.timeout_seconds)
        )
        # 🇺🇸 No `base_url`, no `Authorization`: R2 URLs are presigned and
        # absolute, and sending the vault's bearer token to Cloudflare would
        # leak a credential to a party that has no use for it.
        # 🇧🇷 Sem `base_url`, sem `Authorization`: URLs do R2 são pré-assinadas e
        # absolutas, e mandar o bearer do cofre para a Cloudflare vazaria uma
        # credencial para quem não tem uso para ela.
        self._storage_client = (
            storage_client if storage_client is not None else httpx.Client(timeout=settings.timeout_seconds)
        )
        self._clock = clock if clock is not None else ClockSync()
        self._sleep = sleep

    def close(self) -> None:
        """🇺🇸 Close both underlying `httpx.Client`s. 🇧🇷 Fecha os dois `httpx.Client` internos."""
        self._client.close()
        self._storage_client.close()

    def __enter__(self) -> VaultTransport:
        """🇺🇸 `with VaultTransport(...):` — no setup beyond `__init__`.

        🇧🇷 `with VaultTransport(...):` — sem setup além do `__init__`.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """🇺🇸 Close both clients on the way out, exception or not.

        🇧🇷 Fecha os dois clients na saída, com ou sem exceção.
        """
        self.close()

    def get(self, path: str, *, query: Mapping[str, str | int | bool] | None = None, signed: bool = True) -> Any:
        """🇺🇸 `GET` shortcut for `request`. 🇧🇷 Atalho `GET` para `request`."""
        return self.request("GET", path, query=query, signed=signed)

    def post(
        self,
        path: str,
        *,
        json: Any | None = None,
        query: Mapping[str, str | int | bool] | None = None,
        signed: bool = True,
    ) -> Any:
        """🇺🇸 `POST` shortcut for `request`. 🇧🇷 Atalho `POST` para `request`."""
        return self.request("POST", path, json=json, query=query, signed=signed)

    def put(
        self,
        path: str,
        *,
        json: Any | None = None,
        query: Mapping[str, str | int | bool] | None = None,
        signed: bool = True,
    ) -> Any:
        """🇺🇸 `PUT` shortcut for `request`. 🇧🇷 Atalho `PUT` para `request`."""
        return self.request("PUT", path, json=json, query=query, signed=signed)

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        query: Mapping[str, str | int | bool] | None = None,
        signed: bool = True,
    ) -> Any:
        """🇺🇸 Send one API call, retrying the cases `docs/PROTOCOL.md §12` says are safe to retry.

        Each loop iteration builds a brand new request — a fresh timestamp
        and nonce — because every retry rule here (`ReplayDetected`,
        `SignatureTimestampSkew`) exists precisely because *reusing* a
        `(timestamp, nonce)` pair is what got rejected in the first place.

        🇧🇷 Envia uma chamada de API, retentando os casos que `docs/PROTOCOL.md §12` diz serem seguros.

        Cada volta do laço monta uma requisição nova — timestamp e nonce
        novos — porque toda regra de retentativa aqui (`ReplayDetected`,
        `SignatureTimestampSkew`) existe justamente porque *reusar* um par
        `(timestamp, nonce)` foi o que foi rejeitado da primeira vez.
        """
        body = _encode_json_body(json)
        headers: dict[str, str] = dict(self._token.authorization_header())
        if json is not None:
            headers["Content-Type"] = "application/json"

        replay_retried = False
        skew_retried = False
        server_error_retried = False
        rate_limit_attempts = 0

        while True:
            response = self._send_once(method, path, query=query, body=body, headers=headers, signed=signed)

            if signed:
                self._maybe_deliver_seed(response)

            if response.status_code == 429 and rate_limit_attempts < MAX_RATE_LIMIT_RETRIES:
                wait_seconds = rate_limit_wait_seconds(response, rate_limit_attempts)
                rate_limit_attempts += 1
                self._sleep(wait_seconds)
                continue

            if response.status_code >= 500 and not server_error_retried:
                server_error_retried = True
                self._sleep(SERVER_ERROR_BACKOFF_SECONDS)
                continue

            try:
                return unwrap_result(response)
            except ConflictError as exc:
                if signed and exc.code == "ReplayDetected" and not replay_retried:
                    replay_retried = True
                    continue
                raise
            except AuthenticationError as exc:
                if signed and exc.code == "SignatureTimestampSkew" and not skew_retried:
                    skew_retried = True
                    self._clock.sync(self._client)
                    continue
                raise
