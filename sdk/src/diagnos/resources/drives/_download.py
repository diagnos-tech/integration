"""🇺🇸 `_DownloadMixin`: download/decrypt one node, and decrypt its name — the read half of `Drive`.

Same `self: <Protocol>` typing trick as `_upload.py` — see that module's
docstring for why this is `_DownloadHost`, a structural `Protocol`, and not
`self: Drive` directly.

🇧🇷 `_DownloadMixin`: baixar/decifrar um nó, e decifrar seu nome — a metade de leitura de `Drive`.

Mesmo truque de tipagem `self: <Protocol>` de `_upload.py` — ver a docstring
daquele módulo para o porquê deste ser `_DownloadHost`, um `Protocol`
estrutural, e não `self: Drive` direto.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Protocol

from diagnos.crypto import NODE_NAME_INFO, SecretBox, decrypt_content, decrypt_stream, derive_node_key
from diagnos.models import DriveNode

if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport


class _DownloadHost(Protocol):
    """🇺🇸 What `_DownloadMixin` needs from `Drive` — see the module docstring for why this is a `Protocol`.

    🇧🇷 O que `_DownloadMixin` precisa de `Drive` — ver a docstring do módulo para o porquê de `Protocol`.
    """

    _transport: VaultTransport
    _base: str

    def _group_dek(self) -> SecretBox: ...
    def _sse_headers(self, key: SecretBox) -> dict[str, str]: ...
    def iter_download(self, node_id: str) -> Iterator[bytes]:
        """🇺🇸 Provided by `_DownloadMixin`; `download` builds on it.

        🇧🇷 Fornecido por `_DownloadMixin`; `download` se apoia nele.
        """
        ...


class _DownloadMixin:
    """🇺🇸 The download half of `Drive`: fetch, decrypt, and decrypt the name.

    🇧🇷 A metade de download de `Drive`: buscar, decifrar, e decifrar o nome.
    """

    def iter_download(self: _DownloadHost, node_id: str) -> Iterator[bytes]:
        """🇺🇸 Downloads and decrypts one node lazily, one plaintext chunk at a time.

        Nothing larger than one chunk (1 MiB of ciphertext) is ever held in
        memory, and the first bytes reach the caller before the last ones
        arrive from the vault — what a proxy, a web response or a pipe needs.

        🇧🇷 Baixa e decifra um nó preguiçosamente, um pedaço de texto claro por vez.

        Nada maior que um pedaço (1 MiB de ciphertext) fica na memória, e os
        primeiros bytes chegam a quem chama antes de os últimos saírem do
        cofre — o que um proxy, uma resposta web ou um pipe precisam.
        """
        result = self._transport.get(f"{self._base}/nodes/{node_id}")
        node = DriveNode.model_validate(result["node"])
        node_key = derive_node_key(self._group_dek(), node.node_id)
        # 🇺🇸 SSE-C is never used for multipart (`docs/PROTOCOL.md §10`); a GET
        # has to mirror whatever the original PUT did, or R2 rejects a
        # customer key that was never set on the object.
        # 🇧🇷 SSE-C nunca é usado em multipart (`docs/PROTOCOL.md §10`); um GET
        # precisa espelhar o que o PUT original fez, ou o R2 recusa uma chave
        # de cliente que nunca foi configurada no objeto.
        headers = self._sse_headers(node_key) if node.mode == "single" else {}
        cipher_stream = self._transport.download_stream(result["download"]["url"], headers=headers or None)
        yield from decrypt_stream(node_key, cipher_stream)

    def download(
        self: _DownloadHost,
        node_id: str,
        destination: str | os.PathLike[str] | BinaryIO | None = None,
    ) -> bytes | None:
        """🇺🇸 Downloads and decrypts one node.

        Returns the plaintext bytes when `destination` is `None`; otherwise
        writes them to `destination` and returns `None`. Built on
        `iter_download`, so a file destination is written chunk by chunk.

        🇧🇷 Baixa e decifra um nó.

        Devolve os bytes em texto claro quando `destination` é `None`; senão
        escreve-os em `destination` e devolve `None`. Construído sobre
        `iter_download`, então um destino em arquivo é escrito pedaço a pedaço.
        """
        plaintext_stream = self.iter_download(node_id)
        if destination is None:
            return b"".join(plaintext_stream)
        if isinstance(destination, (str, os.PathLike)):
            with Path(destination).open("wb") as handle:
                for chunk in plaintext_stream:
                    handle.write(chunk)
            return None
        for chunk in plaintext_stream:
            destination.write(chunk)
        return None

    def name_of(self: _DownloadHost, node: DriveNode) -> str | None:
        """🇺🇸 Decrypts `node.encrypted_name` under this drive's group DEK, or `None` if the node has no name on file.

        🇧🇷 Decifra `node.encrypted_name` sob a DEK do grupo deste drive, ou `None` se o nó não tem nome registrado.
        """
        if node.encrypted_name is None:
            return None
        plaintext = decrypt_content(self._group_dek(), node.encrypted_name, NODE_NAME_INFO)
        return plaintext.decode("utf-8")
