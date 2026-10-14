"""`Drives` and `Drive`: the public faces of `_Nodes`, for the workspace's files and for one security group's."""

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
        """Fetch the index of one ready file.

        Args:
            node_id: The node to fetch.

        Returns:
            The node's index. The name stays sealed; open it with `name_of`.

        Raises:
            NotFoundError: If the node is a folder, an unfinished upload, or does not exist.
        """
        return self._nodes.get(node_id)

    def name_of(self, node: DriveNode) -> str:
        """Open the node's sealed file name.

        Args:
            node: A node returned by `get`, `list` or `upload`.

        Returns:
            The file or folder name.

        Raises:
            GroupKeyUnavailable: If this session holds no DEK for the node's security group.
            CryptoError: If the name does not open.
        """
        return self._nodes.name_of(node)

    def iter_download(self, node_id: str) -> Iterator[bytes]:
        """Download and decrypt one file lazily, a plaintext chunk at a time.

        Args:
            node_id: The file to download.

        Yields:
            The plaintext in chunks. Nothing larger than one frame is held in memory.

        Raises:
            NotFoundError: If the node is a folder, an unfinished upload, or does not exist.
            CryptoError: If the body is truncated, tampered with or does not open.
        """
        return self._nodes.iter_download(node_id)

    def download(self, node_id: str, destination: str | os.PathLike[str] | BinaryIO | None = None) -> bytes | None:
        """Download and decrypt one file, returning it or writing it to `destination`.

        Args:
            node_id: The file to download.
            destination: Where to write the plaintext, chunk by chunk: a path or a binary file object. If `None`, the
                whole plaintext is returned instead.

        Returns:
            The plaintext bytes when `destination` is `None`, otherwise `None`.

        Raises:
            NotFoundError: If the node is a folder, an unfinished upload, or does not exist.
            CryptoError: If the body is truncated, tampered with or does not open.
        """
        return self._nodes.download(node_id, destination)


class Drive(_Reading):
    """One security group's files, which is the web app's "drive": list, upload, folders and download."""

    def __init__(self, nodes: _Nodes, security_group_id: str) -> None:
        """Create the drive; callers use `Drives.drive(security_group_id)` instead.

        Args:
            nodes: The shared engine.
            security_group_id: The security group whose files this drive shows.
        """
        self._nodes = nodes
        self._security_group_id = security_group_id

    @property
    def security_group_id(self) -> str:
        """The security group this drive belongs to."""
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
        """Fetch one page of this group's nodes, optionally of one exam or one folder.

        Args:
            exam_id: Only nodes attached to this exam.
            parent_id: Only nodes inside this folder.
            include_pending: Whether to include unfinished uploads.
            limit: The page size.
            cursor: The `next_cursor` of the previous page; `None` for the first page.

        Returns:
            The page of nodes and the cursor for the next one.
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
        """Iterate over every node of this group, across all pages.

        Args:
            exam_id: Only nodes attached to this exam.
            parent_id: Only nodes inside this folder.
            include_pending: Whether to include unfinished uploads.
            limit: The page size used for each request.

        Yields:
            Every matching node.
        """
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
        """Encrypt and upload one file.

        Args:
            source: A path, the file's bytes, or an open binary file.
            name: The file name to seal. It defaults to the path's (or the open file's) file name, and is required
                for `bytes` and anonymous streams.
            mime_type: The MIME type. It defaults to a guess from the name.
            exam_id: Attach the file to this exam.
            parent_id: Place the file in this folder.

        Returns:
            The ready node.

        Raises:
            ValueError: If no file name can be determined.
            GroupKeyUnavailable: If this session holds no DEK for the drive's security group.
            VaultError: If the vault or storage rejects the upload.
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
        """Encrypt and upload a batch of files, reserving 100 at a time.

        Args:
            sources: Paths, bytes, open binary files or `UploadSource` objects.
            exam_id: Attach every file to this exam.
            parent_id: Place every file in this folder.

        Returns:
            The ready nodes, in input order.

        Raises:
            ValueError: If a file name cannot be determined.
            GroupKeyUnavailable: If this session holds no DEK for the drive's security group.
            VaultError: If the vault or storage rejects the upload.
        """
        return self._nodes.upload_many(
            sources, security_group=self._security_group_id, exam_id=exam_id, parent_id=parent_id
        )

    def create_folder(self, name: str, *, parent_id: str | None = None) -> str:
        """Create a folder and return its node id, which can be passed as `parent_id` to upload into it.

        The vault cannot tell two folder names apart (it only sees
        ciphertext), so calling this twice creates two folders.

        Args:
            name: The folder name to seal.
            parent_id: Create the folder inside this folder.

        Returns:
            The new folder's node id.
        """
        return self._nodes.create_folder(name, security_group=self._security_group_id, parent_id=parent_id)


class Drives(_Reading):
    """The workspace's files across groups, plus `drive(group)` for one group's files."""

    def __init__(
        self,
        transport: VaultTransport,
        keyring_provider: Callable[[], Keyring],
        entropy: EntropyMixer,
        *,
        workspace_id: str,
    ) -> None:
        """Create the resource, with one `_Nodes` engine shared by every `Drive` it hands out.

        Args:
            transport: The signed HTTP transport.
            keyring_provider: Returns the live keyring, unlocking the session on first use.
            entropy: The process's entropy mixer, used for new DEKs.
            workspace_id: The workspace whose files are addressed.
        """
        self._nodes = _Nodes(transport, keyring_provider, entropy, workspace_id=workspace_id)

    def drive(self, security_group_id: str) -> Drive:
        """Return the files of one security group.

        Args:
            security_group_id: The security group.

        Returns:
            A `Drive` scoped to that group.
        """
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
        """Fetch one page of the workspace's nodes: every group this session may list, unless filtered.

        Args:
            security_group: Only nodes of this security group.
            exam_id: Only nodes attached to this exam.
            parent_id: Only nodes inside this folder.
            include_pending: Whether to include unfinished uploads.
            limit: The page size.
            cursor: The `next_cursor` of the previous page; `None` for the first page.

        Returns:
            The page of nodes and the cursor for the next one.
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
        """Iterate over every node, across all pages.

        Args:
            security_group: Only nodes of this security group.
            exam_id: Only nodes attached to this exam.
            parent_id: Only nodes inside this folder.
            include_pending: Whether to include unfinished uploads.
            limit: The page size used for each request.

        Yields:
            Every matching node.
        """
        return self._nodes.iter_all(
            security_group=security_group,
            exam_id=exam_id,
            parent_id=parent_id,
            include_pending=include_pending,
            limit=limit,
        )
