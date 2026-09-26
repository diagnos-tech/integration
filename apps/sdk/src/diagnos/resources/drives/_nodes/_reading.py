"""🇺🇸 `_Reading`: list, fetch, open the sealed name, and stream a file's plaintext back.

🇧🇷 `_Reading`: listar, buscar, abrir o nome selado, e devolver o texto claro de um arquivo em stream.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, BinaryIO

from diagnos.crypto import (
    NODE_DEK_INFO,
    NODE_NAME_INFO,
    SecretBox,
    decrypt_content,
    decrypt_stream,
    derive_content_key,
    derive_sse_c_key,
    sse_c_headers,
    unwrap_key,
)
from diagnos.errors import CryptoError
from diagnos.models import DriveNode, Page

from ._base import _NodesBase
from ._support import DEFAULT_PAGE_SIZE


class _Reading(_NodesBase):
    """🇺🇸 The read routes of `_Nodes`: list, get, name, download.

    🇧🇷 As rotas de leitura de `_Nodes`: listar, buscar, nomear, baixar.
    """

    def list(
        self,
        *,
        security_group: str | None = None,
        exam_id: str | None = None,
        parent_id: str | None = None,
        include_pending: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> Page[DriveNode]:
        """🇺🇸 One page of nodes (`GET /nodes`), filtered by group, exam and/or folder.

        🇧🇷 Uma página de nós (`GET /nodes`), filtrada por grupo, exame e/ou pasta.
        """
        query: dict[str, str | int | bool] = {"limit": limit}
        for name, value in (("security_group_id", security_group), ("exam_id", exam_id), ("parent_id", parent_id)):
            if value is not None:
                query[name] = value
        if include_pending:
            query["include_pending"] = "true"
        if cursor is not None:
            query["cursor"] = cursor
        result = self._transport.get(self._base, query=query)
        return Page(
            items=[DriveNode.model_validate(node) for node in result["items"]], next_cursor=result["next_cursor"]
        )

    def iter_all(self, **filters: Any) -> Iterator[DriveNode]:
        """🇺🇸 Walks every page of `list(**filters)`. 🇧🇷 Percorre toda página de `list(**filters)`."""
        cursor: str | None = None
        while True:
            page = self.list(**filters, cursor=cursor)
            yield from page.items
            if page.next_cursor is None:
                return
            cursor = page.next_cursor

    def node_dek(self, node: DriveNode) -> SecretBox:
        """🇺🇸 Unwraps the node's own DEK with the key of its security group.

        🇧🇷 Desembrulha a DEK do próprio nó com a chave do security group dele.
        """
        wrapped = node.encrypted_keys.get(node.security_group_id)
        if wrapped is None:
            raise CryptoError(
                f"🇺🇸 node {node.node_id!r} has no DEK sealed for its own security group {node.security_group_id!r}. "
                f"🇧🇷 o nó {node.node_id!r} não tem DEK selada para o próprio security group {node.security_group_id!r}."
            )
        group_key = self._keyring_provider().group_key(node.security_group_id)
        return unwrap_key(group_key, wrapped, NODE_DEK_INFO)

    def name_of(self, node: DriveNode) -> str:
        """🇺🇸 Opens the node's sealed name. 🇧🇷 Abre o nome selado do nó."""
        return decrypt_content(self.node_dek(node), node.encrypted_name, NODE_NAME_INFO).decode("utf-8")

    def iter_download(self, node_id: str) -> Iterator[bytes]:
        """🇺🇸 Downloads and decrypts one file lazily, a plaintext chunk at a time.

        Nothing larger than one frame is held in memory, and the first bytes
        reach the caller before the last ones leave storage.

        🇧🇷 Baixa e decifra um arquivo preguiçosamente, um pedaço de texto claro por vez.

        Nada maior que um frame fica em memória, e os primeiros bytes chegam
        a quem chama antes de os últimos saírem do armazenamento.
        """
        result = self._transport.get(f"{self._base}/{node_id}")
        node = DriveNode.model_validate(result["node"])
        context = str(result["security_context"]["value"])
        dek = self.node_dek(node)
        download = result["download"]
        headers = {str(k): str(v) for k, v in (download.get("headers") or {}).items()}
        headers.update(sse_c_headers(derive_sse_c_key(dek, node.node_id, context)))
        cipher_stream = self._transport.download_stream(download["url"], headers=headers)
        yield from decrypt_stream(derive_content_key(dek, node.node_id, context), cipher_stream)

    def download(self, node_id: str, destination: str | os.PathLike[str] | BinaryIO | None = None) -> bytes | None:
        """🇺🇸 The whole plaintext when `destination` is `None`; else written to it chunk by chunk.

        🇧🇷 O texto claro inteiro quando `destination` é `None`; senão escrito nele pedaço a pedaço.
        """
        chunks = self.iter_download(node_id)
        if destination is None:
            return b"".join(chunks)
        if isinstance(destination, (str, os.PathLike)):
            with Path(destination).open("wb") as handle:
                for chunk in chunks:
                    handle.write(chunk)
            return None
        for chunk in chunks:
            destination.write(chunk)
        return None
