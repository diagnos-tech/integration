"""`Drives` and `Drive`: the public faces of `_Nodes` — the workspace's files, and one security group's."""

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
    """What both faces share: read one node, open its name, download it."""

    _nodes: _Nodes

    def get(self, node_id: str) -> DriveNode:
        """One ready file's index; folders and unfinished uploads answer `NotFoundError`."""
        return self._nodes.get(node_id)

    def name_of(self, node: DriveNode) -> str:
        """Opens the node's sealed file name."""
        return self._nodes.name_of(node)

    def iter_download(self, node_id: str) -> Iterator[bytes]:
        """Downloads and decrypts one file lazily, a chunk at a time."""
        return self._nodes.iter_download(node_id)

    def download(self, node_id: str, destination: str | os.PathLike[str] | BinaryIO | None = None) -> bytes | None:
        """The plaintext bytes, or written to `destination` (a path or a binary file) chunk by chunk."""
        return self._nodes.download(node_id, destination)


class Drive(_Reading):
    """One security group's files — the web app's "drive": list, upload, folders, download."""

    def __init__(self, nodes: _Nodes, security_group_id: str) -> None:
        """Built by `Drives.drive(security_group_id)`."""
        self._nodes = nodes
        self._security_group_id = security_group_id

    @property
    def security_group_id(self) -> str:
        """The group this drive belongs to."""
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
        """One page of this group's nodes, optionally of one exam or one folder."""
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
        """Every node of this group, across all pages."""
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
        """Uploads one file; `name` defaults to the path's file name, `mime_type` to a guess from it."""
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
        """Uploads a batch (reserved 100 at a time), optionally linked to an exam or placed in a folder."""
        return self._nodes.upload_many(
            sources, security_group=self._security_group_id, exam_id=exam_id, parent_id=parent_id
        )

    def create_folder(self, name: str, *, parent_id: str | None = None) -> str:
        """Creates a folder and returns its node id — pass it as `parent_id` to upload into it.

        The vault cannot tell two folder names apart (it only sees
        ciphertext), so calling this twice creates two folders.
        """
        return self._nodes.create_folder(name, security_group=self._security_group_id, parent_id=parent_id)


class Drives(_Reading):
    """`vault.drives` — the workspace's files across groups, and `drive(group)` for one group's."""

    def __init__(
        self,
        transport: VaultTransport,
        keyring_provider: Callable[[], Keyring],
        entropy: EntropyMixer,
        *,
        workspace_id: str,
    ) -> None:
        """One `_Nodes` engine shared by every `Drive` it hands out."""
        self._nodes = _Nodes(transport, keyring_provider, entropy, workspace_id=workspace_id)

    def drive(self, security_group_id: str) -> Drive:
        """The files of one security group."""
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
        """One page of the workspace's nodes — every group this session may list, unless filtered."""
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
        """Every node, across all pages."""
        return self._nodes.iter_all(
            security_group=security_group,
            exam_id=exam_id,
            parent_id=parent_id,
            include_pending=include_pending,
            limit=limit,
        )
