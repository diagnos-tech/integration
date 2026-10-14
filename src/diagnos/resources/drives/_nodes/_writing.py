"""`_Writing`: seals and stages nodes, then drives the single-`PUT` or multipart body up (`docs/PROTOCOL.md §9`)."""

from __future__ import annotations

import builtins
import uuid
from collections.abc import Iterable
from typing import Any

from diagnos.crypto import (
    NODE_DEK_INFO,
    NODE_NAME_INFO,
    SecretBox,
    encrypt_content,
    encrypted_size,
    generate_dek,
    wrap_key,
)
from diagnos.errors import ProtocolError
from diagnos.models import DriveNode, StagedNode

from .._source import UploadSource
from .._source import _plaintext_source as _plaintext_source
from ._support import MAX_FILES_PER_BATCH, UploadInput, _PreparedUpload
from ._transfer import _Transfer


class _Writing(_Transfer):
    """The write routes of `_Nodes`: folders and batched uploads."""

    def _seal_node(self, group_key: SecretBox, security_group: str, name: str) -> tuple[SecretBox, dict[str, Any]]:
        """Return a fresh node DEK plus the sealed name and wrapped key every stage entry carries."""
        dek = generate_dek(self._entropy)
        entry = {
            "client_ref": uuid.uuid4().hex,
            "encrypted_name": encrypt_content(dek, name.encode("utf-8"), NODE_NAME_INFO).to_dict(),
            "encrypted_keys": {security_group: wrap_key(group_key, dek, NODE_DEK_INFO).to_dict()},
        }
        return dek, entry

    def _stage(self, body: dict[str, Any]) -> builtins.list[StagedNode]:
        """Call `POST /nodes/uploads` to make one reservation for the whole batch (idempotent per `client_ref`)."""
        result = self._transport.post(f"{self._base}/uploads", json=body)
        return [StagedNode.model_validate(item) for item in result["items"]]

    def create_folder(self, name: str, *, security_group: str, parent_id: str | None = None) -> str:
        """Create a folder (ready at once, because it has no content) and return its node id."""
        group_key = self._keyring_provider().group_key(security_group)
        _dek, entry = self._seal_node(group_key, security_group, name)
        body: dict[str, Any] = {"security_group_id": security_group, "files": [{"kind": "folder", **entry}]}
        if parent_id is not None:
            body["parent_id"] = parent_id
        (staged,) = self._stage(body)
        return staged.node_id

    def upload_many(
        self,
        sources: Iterable[UploadInput],
        *,
        security_group: str,
        exam_id: str | None = None,
        parent_id: str | None = None,
    ) -> builtins.list[DriveNode]:
        """Upload every source, in reservations of up to 100, and return the ready nodes in input order."""
        items = [item if isinstance(item, UploadSource) else UploadSource(item) for item in sources]
        group_key = self._keyring_provider().group_key(security_group)
        nodes: builtins.list[DriveNode] = []
        for start in range(0, len(items), MAX_FILES_PER_BATCH):
            batch = items[start : start + MAX_FILES_PER_BATCH]
            nodes.extend(self._upload_batch(batch, group_key, security_group, exam_id, parent_id))
        return nodes

    def _prepare(self, item: UploadSource, group_key: SecretBox, security_group: str) -> _PreparedUpload:
        """Name the file, measure it, and seal what the reservation needs."""
        name = item.resolved_name()
        plaintext = _plaintext_source(item.source)
        dek, entry = self._seal_node(group_key, security_group, name)
        entry["size"] = encrypted_size(plaintext.size)
        mime_type = item.resolved_mime_type(name)
        if mime_type:
            entry["mime_type"] = mime_type
        return _PreparedUpload(client_ref=entry["client_ref"], plaintext=plaintext, dek=dek, stage_entry=entry)

    def _upload_batch(
        self,
        batch: builtins.list[UploadSource],
        group_key: SecretBox,
        security_group: str,
        exam_id: str | None,
        parent_id: str | None,
    ) -> builtins.list[DriveNode]:
        """Stage the batch, upload each file, then confirm the single `PUT` uploads together."""
        prepared = [self._prepare(item, group_key, security_group) for item in batch]
        try:
            body: dict[str, Any] = {
                "security_group_id": security_group,
                "files": [upload.stage_entry for upload in prepared],
            }
            if exam_id is not None:
                body["exam_id"] = exam_id
            if parent_id is not None:
                body["parent_id"] = parent_id
            staged = {node.client_ref: node for node in self._stage(body)}
            finished: dict[str, DriveNode] = {}
            singles: builtins.list[str] = []
            for upload in prepared:
                node = staged.get(upload.client_ref)
                if node is None or node.kind != "file":
                    raise ProtocolError(f"the reservation did not return a file node for {upload.client_ref!r}.")
                if node.mode == "single":
                    self._put_single(node, upload)
                    singles.append(node.node_id)
                elif node.mode == "multipart":
                    finished[node.node_id] = self._put_multipart(node, upload)
                else:
                    raise ProtocolError(f"unknown upload mode {node.mode!r}.")
            finished.update(self._complete_singles(singles))
            # A confirmed node the vault did not echo back is fetched, never assumed.
            node_ids = [staged[upload.client_ref].node_id for upload in prepared]
            return [finished[node_id] if node_id in finished else self.get(node_id) for node_id in node_ids]
        finally:
            for upload in prepared:
                upload.plaintext.cleanup()
