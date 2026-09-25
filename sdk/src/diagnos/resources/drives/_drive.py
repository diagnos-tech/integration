"""🇺🇸 `Drive`/`Drives`: the facade.

Listing lives here directly; `upload`/`upload_many` orchestrate, delegating
the real work to `_upload.py`/`_download.py`.

🇧🇷 `Drive`/`Drives`: a fachada.

A listagem vive aqui direto; `upload`/`upload_many` orquestram, delegando o
trabalho de fato a `_upload.py`/`_download.py`.
"""

from __future__ import annotations

import builtins
import os
from collections.abc import Callable, Iterable, Iterator
from typing import TYPE_CHECKING, BinaryIO

from diagnos.crypto import EntropyMixer, SecretBox, derive_node_key, derive_sse_c_key, sse_c_headers
from diagnos.models import DriveNode, Page
from diagnos.session.keyring import Keyring

from ._download import _DownloadMixin
from ._source import UploadSource
from ._upload import _UploadMixin

if TYPE_CHECKING:
    from diagnos.transport.config import Settings
    from diagnos.transport.http import VaultTransport

# 🇺🇸 `builtins.list[...]`, not the bare generic: `Drive` defines a method
# literally named `list`, and mypy (with `from __future__ import annotations`)
# resolves a later bare `list` to that method instead of the builtin type.
# 🇧🇷 `builtins.list[...]`, não o genérico cru: `Drive` define um método
# chamado exatamente `list`, e o mypy (com `from __future__ import annotations`)
# resolve um `list` cru mais adiante para esse método, não para o tipo embutido.


class Drive(_UploadMixin, _DownloadMixin):
    """🇺🇸 One security group's files: list, upload, download, name.

    🇧🇷 Os arquivos de um security group: listar, subir, baixar, nomear.
    """

    def __init__(
        self,
        transport: VaultTransport,
        keyring_provider: Callable[[], Keyring],
        entropy: EntropyMixer,
        *,
        workspace_id: str,
        security_group_id: str,
        settings: Settings,
    ) -> None:
        """🇺🇸 Built by `Drives.drive(security_group_id)`, never directly by a caller.

        🇧🇷 Construído por `Drives.drive(security_group_id)`, nunca direto por quem chama.
        """
        self._transport = transport
        self._keyring_provider = keyring_provider
        self._entropy = entropy
        self._security_group_id = security_group_id
        self._settings = settings
        self._base = f"/api/external/v1/workspaces/{workspace_id}/drives/{security_group_id}"

    def _group_dek(self) -> SecretBox:
        """🇺🇸 This drive's own security group DEK, straight from the keyring.

        🇧🇷 A DEK do security group deste drive, direto do keyring.
        """
        return self._keyring_provider().group_key(self._security_group_id)

    def _sse_headers(self, key: SecretBox) -> dict[str, str]:
        """🇺🇸 The three SSE-C headers when `settings.sse_c` is on, else nothing (`docs/PROTOCOL.md §10`).

        🇧🇷 Os três headers de SSE-C quando `settings.sse_c` está ligado, senão nada (`docs/PROTOCOL.md §10`).
        """
        if not self._settings.sse_c:
            return {}
        return sse_c_headers(derive_sse_c_key(key))

    # -- listing -------------------------------------------------------------

    def list(
        self,
        *,
        exam_id: str | None = None,
        include_pending: bool = False,
        limit: int = 50,
        cursor: str | None = None,
    ) -> Page[DriveNode]:
        """🇺🇸 One page of nodes (`GET {base}/nodes`, `docs/PROTOCOL.md §9`).

        🇧🇷 Uma página de nós (`GET {base}/nodes`, `docs/PROTOCOL.md §9`).
        """
        query: dict[str, str | int | bool] = {"limit": limit}
        if exam_id is not None:
            query["exam_id"] = exam_id
        if include_pending:
            query["include_pending"] = True
        if cursor is not None:
            query["cursor"] = cursor
        result = self._transport.get(f"{self._base}/nodes", query=query)
        items = [DriveNode.model_validate(node) for node in result["items"]]
        return Page(items=items, next_cursor=result.get("next_cursor"))

    def iter_all(
        self,
        *,
        exam_id: str | None = None,
        include_pending: bool = False,
        limit: int = 50,
    ) -> Iterator[DriveNode]:
        """🇺🇸 Walks every page by following `next_cursor` until it is `None`.

        🇧🇷 Percorre toda página seguindo `next_cursor` até ele ser `None`.
        """
        cursor: str | None = None
        while True:
            page = self.list(exam_id=exam_id, include_pending=include_pending, limit=limit, cursor=cursor)
            yield from page.items
            if page.next_cursor is None:
                return
            cursor = page.next_cursor

    def get(self, node_id: str) -> DriveNode:
        """🇺🇸 One node's index, discarding the attached download URL (`GET {base}/nodes/{id}`).

        🇧🇷 O índice de um nó, descartando a URL de download anexada (`GET {base}/nodes/{id}`).
        """
        result = self._transport.get(f"{self._base}/nodes/{node_id}")
        return DriveNode.model_validate(result["node"])

    # -- upload ----------------------------------------------------------------

    def upload(
        self,
        source: str | os.PathLike[str] | bytes | BinaryIO,
        *,
        name: str | None = None,
        mime_type: str | None = None,
        exam_id: str | None = None,
    ) -> DriveNode:
        """🇺🇸 Uploads one file — a thin wrapper over `upload_many` with a single-item batch.

        🇧🇷 Sobe um arquivo — uma casca fina sobre `upload_many` com um lote de um item.
        """
        [node] = self.upload_many([UploadSource(source, name=name, mime_type=mime_type)], exam_id=exam_id)
        return node

    def upload_many(
        self,
        sources: Iterable[UploadSource | str | os.PathLike[str] | bytes | BinaryIO],
        *,
        exam_id: str | None = None,
    ) -> builtins.list[DriveNode]:
        """🇺🇸 Stages the whole batch in one call (`docs/PROTOCOL.md §9`, ≤1000 files), then uploads each file.

        Single-mode files are confirmed together in one
        `uploads/complete {node_ids}` call after every PUT lands; each
        multipart file is confirmed on its own, since multipart's completion
        endpoint is per-node.

        🇧🇷 Reserva o lote inteiro numa chamada (`docs/PROTOCOL.md §9`, ≤1000
        arquivos), depois sobe cada arquivo.

        Arquivos single são confirmados juntos, numa única chamada
        `uploads/complete {node_ids}`, depois que todo PUT termina; cada
        arquivo multipart é confirmado por conta própria, já que o endpoint
        de conclusão de multipart é por nó.
        """
        items = [item if isinstance(item, UploadSource) else UploadSource(item) for item in sources]
        if not items:
            return []

        group_dek = self._group_dek()
        prepared = [self._prepare_upload(item, group_dek) for item in items]
        try:
            staged_by_ref = {node.client_ref: node for node in self._stage_batch(prepared, exam_id)}
            single_node_ids: builtins.list[str] = []
            node_ids: builtins.list[str] = []
            for request in prepared:
                staged = staged_by_ref[request.client_ref]
                node_key = derive_node_key(group_dek, staged.node_id)
                if staged.mode == "single":
                    self._put_single(staged, node_key, request.plaintext)
                    single_node_ids.append(staged.node_id)
                else:
                    self._put_multipart(staged, node_key, request.plaintext)
                node_ids.append(staged.node_id)
            if single_node_ids:
                self._complete_single(single_node_ids)
            return [self.get(node_id) for node_id in node_ids]
        finally:
            for request in prepared:
                request.plaintext.cleanup()


class Drives:
    """🇺🇸 `vault.drives` — the factory that hands out one `Drive` per security group.

    🇧🇷 `vault.drives` — a fábrica que entrega um `Drive` por security group.
    """

    def __init__(
        self,
        transport: VaultTransport,
        keyring_provider: Callable[[], Keyring],
        entropy: EntropyMixer,
        *,
        workspace_id: str,
        settings: Settings,
    ) -> None:
        """🇺🇸 Holds what every `Drive` needs, so `drive(...)` itself takes only the group id.

        🇧🇷 Guarda o que todo `Drive` precisa, para `drive(...)` em si só receber o id do grupo.
        """
        self._transport = transport
        self._keyring_provider = keyring_provider
        self._entropy = entropy
        self._workspace_id = workspace_id
        self._settings = settings

    def drive(self, security_group_id: str) -> Drive:
        """🇺🇸 A `Drive` scoped to one security group. 🇧🇷 Um `Drive` restrito a um security group."""
        return Drive(
            self._transport,
            self._keyring_provider,
            self._entropy,
            workspace_id=self._workspace_id,
            security_group_id=security_group_id,
            settings=self._settings,
        )
