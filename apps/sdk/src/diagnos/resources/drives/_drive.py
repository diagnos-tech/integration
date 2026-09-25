"""🇺🇸 `Drives` and `Drive`: the public faces of `_Nodes` — the workspace's files, and one security group's.

🇧🇷 `Drives` e `Drive`: as faces públicas de `_Nodes` — os arquivos do workspace, e os de um security group.
"""

from __future__ import annotations

import builtins
import os
from collections.abc import Callable, Iterable, Iterator
from typing import TYPE_CHECKING, BinaryIO

from diagnos.crypto import EntropyMixer
from diagnos.models import DriveNode, Page
from diagnos.session.keyring import Keyring

from ._nodes import DEFAULT_PAGE_SIZE, UploadInput, _Nodes
from ._source import UploadSource

if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport


class _Reading:
    """🇺🇸 What both faces share: read one node, open its name, download it.

    🇧🇷 O que as duas faces compartilham: ler um nó, abrir o nome, baixá-lo.
    """

    _nodes: _Nodes

    def get(self, node_id: str) -> DriveNode:
        """🇺🇸 One ready file's index; folders and unfinished uploads answer `NotFoundError`.

        🇧🇷 O índice de um arquivo pronto; pastas e uploads inacabados respondem `NotFoundError`.
        """
        return self._nodes.get(node_id)

    def name_of(self, node: DriveNode) -> str:
        """🇺🇸 Opens the node's sealed file name. 🇧🇷 Abre o nome de arquivo selado do nó."""
        return self._nodes.name_of(node)

    def iter_download(self, node_id: str) -> Iterator[bytes]:
        """🇺🇸 Downloads and decrypts one file lazily, a chunk at a time. 🇧🇷 Baixa e decifra um arquivo aos pedaços."""
        return self._nodes.iter_download(node_id)

    def download(self, node_id: str, destination: str | os.PathLike[str] | BinaryIO | None = None) -> bytes | None:
        """🇺🇸 The plaintext bytes, or written to `destination` (a path or a binary file) chunk by chunk.

        🇧🇷 Os bytes em texto claro, ou escritos em `destination` (um path ou um arquivo binário) aos pedaços.
        """
        return self._nodes.download(node_id, destination)


class Drive(_Reading):
    """🇺🇸 One security group's files — the web app's "drive": list, upload, folders, download.

    🇧🇷 Os arquivos de um security group — o "drive" do app web: listar, subir, pastas, baixar.
    """

    def __init__(self, nodes: _Nodes, security_group_id: str) -> None:
        """🇺🇸 Built by `Drives.drive(security_group_id)`. 🇧🇷 Construído por `Drives.drive(security_group_id)`."""
        self._nodes = nodes
        self._security_group_id = security_group_id

    @property
    def security_group_id(self) -> str:
        """🇺🇸 The group this drive belongs to. 🇧🇷 O grupo a que este drive pertence."""
        return self._security_group_id

    def list(
        self,
        *,
        exam_id: str | None = None,
        parent_id: str | None = None,
        include_pending: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> Page[DriveNode]:
        """🇺🇸 One page of this group's nodes, optionally of one exam or one folder.

        🇧🇷 Uma página dos nós deste grupo, opcionalmente de um exame ou de uma pasta.
        """
        return self._nodes.list(
            security_group=self._security_group_id,
            exam_id=exam_id,
            parent_id=parent_id,
            include_pending=include_pending,
            limit=limit,
            cursor=cursor,
        )

    def iter_all(
        self,
        *,
        exam_id: str | None = None,
        parent_id: str | None = None,
        include_pending: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[DriveNode]:
        """🇺🇸 Every node of this group, across all pages. 🇧🇷 Todo nó deste grupo, por todas as páginas."""
        return self._nodes.iter_all(
            security_group=self._security_group_id,
            exam_id=exam_id,
            parent_id=parent_id,
            include_pending=include_pending,
            limit=limit,
        )

    def upload(
        self,
        source: str | os.PathLike[str] | bytes | BinaryIO,
        *,
        name: str | None = None,
        mime_type: str | None = None,
        exam_id: str | None = None,
        parent_id: str | None = None,
    ) -> DriveNode:
        """🇺🇸 Uploads one file; `name` defaults to the path's file name, `mime_type` to a guess from it.

        🇧🇷 Sobe um arquivo; `name` é, por padrão, o nome do arquivo do path, e `mime_type` um palpite por ele.
        """
        [node] = self.upload_many(
            [UploadSource(source, name=name, mime_type=mime_type)], exam_id=exam_id, parent_id=parent_id
        )
        return node

    def upload_many(
        self,
        sources: Iterable[UploadInput],
        *,
        exam_id: str | None = None,
        parent_id: str | None = None,
    ) -> builtins.list[DriveNode]:
        """🇺🇸 Uploads a batch (reserved 100 at a time), optionally linked to an exam or placed in a folder.

        🇧🇷 Sobe um lote (reservado de 100 em 100), opcionalmente ligado a um exame ou dentro de uma pasta.
        """
        return self._nodes.upload_many(
            sources, security_group=self._security_group_id, exam_id=exam_id, parent_id=parent_id
        )

    def create_folder(self, name: str, *, parent_id: str | None = None) -> str:
        """🇺🇸 Creates a folder and returns its node id — pass it as `parent_id` to upload into it.

        The vault cannot tell two folder names apart (it only sees
        ciphertext), so calling this twice creates two folders.

        🇧🇷 Cria uma pasta e devolve o id do nó — passe-o como `parent_id` para subir dentro dela.

        O cofre não distingue dois nomes de pasta (só vê ciphertext), então
        chamar isto duas vezes cria duas pastas.
        """
        return self._nodes.create_folder(name, security_group=self._security_group_id, parent_id=parent_id)


class Drives(_Reading):
    """🇺🇸 `vault.drives` — the workspace's files across groups, and `drive(group)` for one group's.

    🇧🇷 `vault.drives` — os arquivos do workspace entre grupos, e `drive(grupo)` para os de um grupo.
    """

    def __init__(
        self,
        transport: VaultTransport,
        keyring_provider: Callable[[], Keyring],
        entropy: EntropyMixer,
        *,
        workspace_id: str,
    ) -> None:
        """🇺🇸 One `_Nodes` engine shared by every `Drive` it hands out. 🇧🇷 Um motor `_Nodes` compartilhado."""
        self._nodes = _Nodes(transport, keyring_provider, entropy, workspace_id=workspace_id)

    def drive(self, security_group_id: str) -> Drive:
        """🇺🇸 The files of one security group. 🇧🇷 Os arquivos de um security group."""
        return Drive(self._nodes, security_group_id)

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
        """🇺🇸 One page of the workspace's nodes — every group this session may list, unless filtered.

        🇧🇷 Uma página dos nós do workspace — todo grupo que esta sessão pode listar, salvo filtro.
        """
        return self._nodes.list(
            security_group=security_group,
            exam_id=exam_id,
            parent_id=parent_id,
            include_pending=include_pending,
            limit=limit,
            cursor=cursor,
        )

    def iter_all(
        self,
        *,
        security_group: str | None = None,
        exam_id: str | None = None,
        parent_id: str | None = None,
        include_pending: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[DriveNode]:
        """🇺🇸 Every node, across all pages. 🇧🇷 Todo nó, por todas as páginas."""
        return self._nodes.iter_all(
            security_group=security_group,
            exam_id=exam_id,
            parent_id=parent_id,
            include_pending=include_pending,
            limit=limit,
        )
