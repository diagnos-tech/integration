"""The drive half of the fake vault: nodes (files and folders), shared across every security group.

Split out of `fakes.py` purely to keep that module under the file-size limit; `FakeDiagnos.drives` (in `fakes.py`)
wires a `FakeDrives` in.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, BinaryIO

from diagnos import DriveNode, GroupKeyUnavailable, NotFoundError, Page

WORKSPACE_ID = "ws_test"


class _NodeStore:
    """The one in-memory store that every `FakeDrive` shares, because the vault addresses a node by id across groups."""

    def __init__(self) -> None:
        """Starts empty."""
        self.nodes: dict[str, DriveNode] = {}
        self.data: dict[str, bytes] = {}
        self.names: dict[str, str] = {}
        self.counter = 0

    def add(self, security_group_id: str, name: str, *, kind: str = "file", data: bytes = b"", **fields: Any) -> str:
        """Stores one node and returns its id."""
        self.counter += 1
        node_id = f"node_{self.counter}"
        self.nodes[node_id] = DriveNode.model_validate(
            {
                "node_id": node_id,
                "workspace_id": WORKSPACE_ID,
                "security_group_id": security_group_id,
                "kind": kind,
                "status": "ready",
                "encrypted_name": {"salt": "s", "nonce": "n", "ciphertext": "c"},
                "encrypted_keys": {},
                "created_by": "tester",
                "created_at": "2024-01-01T00:00:00Z",
                **fields,
            }
        )
        self.data[node_id] = data
        self.names[node_id] = name
        return node_id


class _FakeReading:
    """The read half both `Drive` and `Drives` expose (`resources/drives/_drive.py`'s `_Reading`)."""

    def __init__(self, store: _NodeStore) -> None:
        """Reads from `store`; `locked` acts like a session holding no key for any group."""
        self._store = store
        self.locked = False

    def get(self, node_id: str) -> DriveNode:
        """Returns the stored `DriveNode`, or raises `NotFoundError`."""
        try:
            return self._store.nodes[node_id]
        except KeyError:
            raise NotFoundError(code="DriveNodeNotFound", message=f"no node {node_id!r}", status=404) from None

    def name_of(self, node: DriveNode) -> str:
        """Returns the plaintext name stored for this node."""
        if self.locked:
            raise GroupKeyUnavailable(f"no key for {node.security_group_id!r}")
        return self._store.names[node.node_id]

    def iter_download(self, node_id: str) -> Iterator[bytes]:
        """Yields the stored bytes in two chunks, like the SDK's lazy decryptor."""
        data = self._store.data[self.get(node_id).node_id]
        half = len(data) // 2
        yield data[:half]
        yield data[half:]


class FakeDrive(_FakeReading):
    """Enough of `Drive` (`apps/sdk/src/diagnos/resources/drives/`) for the routes in `routers/files.py`."""

    def __init__(self, store: _NodeStore, security_group_id: str) -> None:
        """`calls` records every keyword the routes forwarded, so a test can assert the HTTP → SDK mapping."""
        super().__init__(store)
        self.security_group_id = security_group_id
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list(self, **kwargs: Any) -> Page[DriveNode]:
        """Returns every stored node of this group."""
        self.calls.append(("list", kwargs))
        items = [node for node in self._store.nodes.values() if node.security_group_id == self.security_group_id]
        return Page(items=items, next_cursor="cursor_2" if kwargs.get("limit") == 1 else None)

    def upload(
        self,
        source: str | os.PathLike[str] | bytes | BinaryIO,
        *,
        name: str | None = None,
        mime_type: str | None = None,
        exam_id: str | None = None,
        parent_id: str | None = None,
    ) -> DriveNode:
        """Reads `source` fully (mirroring `Drive.upload`'s accepted input shapes) and stores it as a node."""
        if isinstance(source, bytes):
            data = source
        elif isinstance(source, (str, os.PathLike)):
            data = Path(source).read_bytes()
        else:
            data = source.read()
        self.calls.append(
            ("upload", {"data": data, "name": name, "mime_type": mime_type, "exam_id": exam_id, "parent_id": parent_id})
        )
        node_id = self._store.add(
            self.security_group_id,
            name or "",
            data=data,
            exam_id=exam_id,
            parent_id=parent_id,
            mode="single",
            size=len(data),
            declared_size=len(data),
            mime_type=mime_type,
        )
        return self._store.nodes[node_id]

    def create_folder(self, name: str, *, parent_id: str | None = None) -> str:
        """Stores a folder node and returns its id, like `Drive.create_folder`."""
        self.calls.append(("create_folder", {"name": name, "parent_id": parent_id}))
        return self._store.add(self.security_group_id, name, kind="folder", parent_id=parent_id)


class FakeDrives(_FakeReading):
    """Enough of `Drives` to read any node by id and hand out one `FakeDrive` per group."""

    def __init__(self) -> None:
        """Starts empty; a `FakeDrive` is created on first request per security group."""
        self.store = _NodeStore()
        super().__init__(self.store)
        self._drives: dict[str, FakeDrive] = {}

    def drive(self, security_group_id: str) -> FakeDrive:
        """Returns the same `FakeDrive` instance for a given `security_group_id`, across calls."""
        if security_group_id not in self._drives:
            self._drives[security_group_id] = FakeDrive(self.store, security_group_id)
        return self._drives[security_group_id]
