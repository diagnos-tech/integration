"""🇺🇸 `_StorageMixin`: direct R2 object-storage access — no base URL, no `Authorization`, no signature.

`VaultTransport` mixes this in for `upload_bytes`/`download_bytes`/
`download_stream`; none of the three need signing, session state, or retry
(that all lives in `http.py`), so splitting them out here is what keeps
`http.py` down to just what does. Its methods take `self: _StorageHost`, a
structural `Protocol` naming just `_storage_client` — not `self:
VaultTransport` itself, because mypy requires an explicit self-type to be a
*supertype* of the defining class, and `VaultTransport` (which inherits this
mixin) is the other way round: a subtype of it.

🇧🇷 `_StorageMixin`: acesso direto ao armazenamento de objetos do R2 — sem base URL, sem `Authorization`, sem assinatura.

`VaultTransport` mistura isto para `upload_bytes`/`download_bytes`/
`download_stream`; nenhum dos três precisa de assinatura, estado de sessão
ou retentativa (isso tudo vive em `http.py`), então separá-los aqui é o que
mantém `http.py` restrito a só o que assina/envia. Seus métodos recebem
`self: _StorageHost`, um `Protocol` estrutural que só nomeia
`_storage_client` — não `self: VaultTransport` em si, porque o mypy exige
que um self-type explícito seja um *supertipo* da classe que o define, e
`VaultTransport` (que herda este mixin) é o contrário disso: um subtipo dele.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Protocol

import httpx

from diagnos.errors import VaultError


class _StorageHost(Protocol):
    """🇺🇸 What `_StorageMixin` needs from `VaultTransport` — see the module docstring for why this is a `Protocol`.

    🇧🇷 O que `_StorageMixin` precisa de `VaultTransport` — ver a docstring do módulo para o porquê de `Protocol`.
    """

    _storage_client: httpx.Client


class _StorageMixin:
    """🇺🇸 The R2 half of `VaultTransport`: `upload_bytes`, `download_bytes`, `download_stream`.

    🇧🇷 A metade de R2 de `VaultTransport`: `upload_bytes`, `download_bytes`, `download_stream`.
    """

    def upload_bytes(
        self: _StorageHost, url: str, data: bytes | Iterable[bytes], headers: Mapping[str, str]
    ) -> str | None:
        """🇺🇸 `PUT` straight to R2 — no `Authorization`, no signature, `headers` exactly as the vault issued them.

        Returns the `ETag` the multipart-complete step later needs.

        🇧🇷 `PUT` direto no R2 — sem `Authorization`, sem assinatura, `headers` exatamente como o cofre emitiu.

        Retorna o `ETag` que o passo de completar multipart precisa depois.
        """
        response = self._storage_client.put(url, content=data, headers=dict(headers))
        _raise_for_storage_error(response)
        etag: str | None = response.headers.get("ETag")
        return etag

    def download_bytes(self: _StorageHost, url: str, headers: Mapping[str, str] | None = None) -> bytes:
        """🇺🇸 `GET` straight from R2 and buffer the whole body.

        🇧🇷 `GET` direto do R2 e junta o corpo inteiro.
        """
        response = self._storage_client.get(url, headers=dict(headers) if headers else None)
        _raise_for_storage_error(response)
        return response.content

    def download_stream(self: _StorageHost, url: str, headers: Mapping[str, str] | None = None) -> Iterator[bytes]:
        """🇺🇸 `GET` straight from R2, yielding chunks without buffering the whole body.

        For the framed drive bodies (`docs/PROTOCOL.md §9`) this lets the
        caller reassemble `secretstream` frames without holding a 64 MiB
        object in memory at once.

        🇧🇷 `GET` direto do R2, entregando pedaços sem juntar o corpo inteiro.

        Para os corpos framed de drive (`docs/PROTOCOL.md §9`), isso deixa
        quem chama remontar os frames do `secretstream` sem segurar um objeto
        de 64 MiB inteiro na memória de uma vez.
        """
        with self._storage_client.stream("GET", url, headers=dict(headers) if headers else None) as response:
            _raise_for_storage_error(response)
            yield from response.iter_bytes()


def _raise_for_storage_error(response: httpx.Response) -> None:
    """🇺🇸 R2 speaks plain HTTP status, not the vault's envelope — no `code` to read.

    🇧🇷 O R2 fala status HTTP puro, não o envelope do cofre — não há `code` para ler.
    """
    if 200 <= response.status_code < 300:
        return
    raise VaultError(
        code="StorageError",
        message=(
            f"🇺🇸 object storage answered HTTP {response.status_code}. "
            f"🇧🇷 o armazenamento de objetos respondeu HTTP {response.status_code}."
        ),
        status=response.status_code,
    )
