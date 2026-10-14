"""`_Writing`: the two-phase write path (seal, reserve, `PUT`, commit) plus the patch-only flag flip."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import httpx

from diagnos.crypto import (
    DOCUMENT_DEK_INFO,
    SEALED_OVERHEAD_BYTES,
    SecretBox,
    generate_dek,
    seal_version_content,
    wrap_key,
)
from diagnos.errors import ConflictError, ProtocolError, VaultError
from diagnos.models import DocumentIndex

from ._base import _DocumentsBase
from ._support import (
    _SSE_C_HEADER_PREFIX,
    COMMIT_ATTEMPTS,
    COMMIT_BACKOFF_SECONDS,
    DATA_STREAM,
    STAGE_PENDING_ATTEMPTS,
    STAGE_PENDING_BACKOFF_SECONDS,
    OpenedDocument,
    RecordT,
    SummaryT,
    _is_retryable_commit_failure,
)


class _Writing(_DocumentsBase[RecordT, SummaryT]):
    """The create/update/flag routes of `VersionedDocuments`."""

    # -- writing -------------------------------------------------------------

    @staticmethod
    def _serialize(record: RecordT) -> bytes:
        """Serialize the record as JSON, leaving absent fields out (`exclude_none`), as the web app writes it."""
        return record.model_dump_json(exclude_none=True).encode("utf-8")

    @staticmethod
    def _put_headers(upload: Mapping[str, Any]) -> dict[str, str]:
        """Return the `PUT` headers: what the vault fixed (`content-length`), minus SSE-C.

        The vault also names SSE-C headers for documents, but the web app
        does not use SSE-C on documents: it neither sends the key on the
        `PUT` nor on the `GET`. An object stored with SSE-C could only be
        read with that key, so the web app could never open a document the
        SDK wrote that way. Leaving the whole SSE-C trio out keeps both sides
        reading the same plain object (the body is end-to-end encrypted
        either way; SSE-C was only ever a second layer).
        """
        headers = upload.get("headers") or {}
        return {
            name: str(value) for name, value in headers.items() if not name.lower().startswith(_SSE_C_HEADER_PREFIX)
        }

    def _upload(self, staged: Mapping[str, Any], dek: SecretBox, plaintext: bytes) -> None:
        """Seal `plaintext` for the reserved version and `PUT` it to the signed URL."""
        sealed = seal_version_content(dek, staged["version_id"], staged["security_context"]["value"], plaintext)
        headers = self._put_headers(staged["upload"])
        declared = headers.get("content-length")
        if declared is not None and int(declared) != len(sealed):
            raise ProtocolError(f"the vault signed {declared} bytes but the sealed version has {len(sealed)}.")
        self._transport.upload_bytes(staged["upload"]["url"], sealed, headers)

    def _stage(self, document_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """`POST {stream}/versions`, retrying briefly while another writer holds the pending slot."""
        path = f"{self._stream_path(document_id)}/versions"
        for attempt in range(1, STAGE_PENDING_ATTEMPTS + 1):
            try:
                result: dict[str, Any] = self._transport.post(path, json=dict(body))
                return result
            except ConflictError as exc:
                if exc.code != "DocumentVersionPending" or attempt == STAGE_PENDING_ATTEMPTS:
                    raise
                self._sleep(STAGE_PENDING_BACKOFF_SECONDS * attempt)
        raise AssertionError("unreachable")  # pragma: no cover

    def _commit(self, document_id: str, version_id: str) -> DocumentIndex:
        """`POST {stream}/versions/{version_id}/commit`, retried with backoff because a replay is idempotent."""
        path = f"{self._stream_path(document_id)}/versions/{version_id}/commit"
        for attempt in range(1, COMMIT_ATTEMPTS + 1):
            try:
                result = self._transport.post(path)
                return DocumentIndex.model_validate(result["document"])
            except (httpx.TransportError, VaultError) as exc:
                if not _is_retryable_commit_failure(exc) or attempt == COMMIT_ATTEMPTS:
                    raise
                self._sleep(COMMIT_BACKOFF_SECONDS * 2 ** (attempt - 1))
        raise AssertionError("unreachable")  # pragma: no cover

    def create(
        self,
        record: RecordT,
        *,
        security_group: str,
        summary: SummaryT,
        meta: Mapping[str, Any] | None = None,
    ) -> OpenedDocument[RecordT, SummaryT]:
        """Create a document: a fresh DEK sealed for `security_group`, then reserve, `PUT` and commit the first version.

        Args:
            record: The record to seal as the first version.
            security_group: The single security group that will own the document.
            summary: The list summary to seal in `encrypted_index`.
            meta: Clear metadata the vault itself reads, if any.

        Returns:
            The new document's index, record, summary and first version id.

        Raises:
            GroupKeyUnavailable: If this session holds no DEK for `security_group`.
            VaultError: If the vault rejects the reservation or the commit.
        """
        keyring = self._keyring_provider()
        group_key = keyring.group_key(security_group)
        dek = generate_dek(self._entropy)
        plaintext = self._serialize(record)
        body: dict[str, Any] = {
            "security_group_id": security_group,
            "encrypted_keys": {security_group: wrap_key(group_key, dek, DOCUMENT_DEK_INFO).to_dict()},
            "content_length": len(plaintext) + SEALED_OVERHEAD_BYTES,
            "encrypted_index": self._seal_summary(dek, summary),
            "stream": DATA_STREAM,
        }
        if meta:
            body["meta"] = dict(meta)
        staged = self._transport.post(self._base, json=body)
        document_id = str(staged["document"]["document_id"])
        self._upload(staged, dek, plaintext)
        index = self._commit(document_id, str(staged["version_id"]))
        return OpenedDocument(index, record, summary, version_id=str(staged["version_id"]))

    def update(
        self,
        document_id: str,
        record: RecordT,
        *,
        summary: Callable[[SummaryT | None], SummaryT],
        meta: Mapping[str, Any] | None = None,
        expected_latest_version_id: str | None = None,
    ) -> OpenedDocument[RecordT, SummaryT]:
        """Write a new complete version of `record`, sealed under the document's existing DEK.

        Args:
            document_id: The document to update.
            record: The complete new record.
            summary: Maps the current summary (or `None`) to the new one, so a resource can carry forward what is not
                part of the record, such as a patient's `tags`.
            meta: Clear metadata to set, if any.
            expected_latest_version_id: If given, the vault refuses the write when someone else committed a version
                since you read it.

        Returns:
            The updated index, record, summary and the new version id.

        Raises:
            ConflictError: With `code` `"DocumentVersionMismatch"` when `expected_latest_version_id` is stale.
            ProtocolError: If the vault answers the reservation inconsistently.
            VaultError: If the vault rejects the reservation or the commit.
        """
        keyring = self._keyring_provider()  # lazy unlock first (see `list`)
        index = self.get_index(document_id)
        dek = self._document_dek(index, keyring)
        new_summary = summary(self._open_summary(index, dek))
        plaintext = self._serialize(record)
        body: dict[str, Any] = {
            "content_length": len(plaintext) + SEALED_OVERHEAD_BYTES,
            "encrypted_index": self._seal_summary(dek, new_summary),
        }
        if meta:
            body["meta"] = dict(meta)
        if expected_latest_version_id is not None:
            body["expected_latest_version_id"] = expected_latest_version_id
        staged = self._stage(document_id, body)
        if staged.get("staged") is not True:
            raise ProtocolError("the vault answered a version reservation as patch-only.")
        self._upload(staged, dek, plaintext)
        committed = self._commit(document_id, str(staged["version_id"]))
        return OpenedDocument(committed, record, new_summary, version_id=str(staged["version_id"]))

    def set_flags(
        self, document_id: str, *, is_archived: bool | None = None, is_deleted: bool | None = None
    ) -> DocumentIndex:
        """Flip `is_archived` or `is_deleted` in place with a patch-only reservation (no version, no upload)."""
        self._keyring_provider()  # lazy unlock before signing (see `list`)
        body = {
            name: value
            for name, value in (("is_archived", is_archived), ("is_deleted", is_deleted))
            if value is not None
        }
        result = self._transport.post(f"{self._stream_path(document_id)}/versions", json=body)
        return DocumentIndex.model_validate(result["document"])
