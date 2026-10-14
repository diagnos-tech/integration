"""`_DocumentsBase`: construction, URL shape and key handling shared by the read and write mixins.

`_Reading` (`_reading.py`) and `_Writing` (`_writing.py`) both need the same
document's DEK, the same `{base}[/streams/data]` URL shape, and the same
constructor state (`transport`, `keyring_provider`, ...). This is the one
place that state and those two small protocol quirks live, so
`VersionedDocuments` (`__init__.py`) is just `_Reading` and `_Writing`
stitched together.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Generic

from diagnos.crypto import (
    DOCUMENT_DEK_INFO,
    INDEX_INFO,
    EntropyMixer,
    SecretBox,
    decrypt_content,
    encrypt_content,
    unwrap_key,
)
from diagnos.errors import CryptoError
from diagnos.models import DocumentIndex, DocumentListItem, ResourceKind
from diagnos.session.keyring import Keyring

from ._support import DATA_STREAM, STREAMS_BY_RESOURCE, RecordT, SummaryT

if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport


class _DocumentsBase(Generic[RecordT, SummaryT]):
    """One resource (`patients`, `exams` or `templates`) of one workspace, generic over record and summary types."""

    def __init__(
        self,
        transport: VaultTransport,
        keyring_provider: Callable[[], Keyring],
        entropy: EntropyMixer,
        *,
        workspace_id: str,
        resource: ResourceKind,
        record_model: type[RecordT],
        summary_model: type[SummaryT],
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Bind the engine to one resource of one workspace.

        `keyring_provider` is a callback (not a `Keyring`) so that a lazy,
        auto-unlocking caller always asks fresh.

        Args:
            transport: The signed HTTP transport.
            keyring_provider: Returns the live keyring, unlocking the session on first use.
            entropy: The process's entropy mixer, used for new DEKs.
            workspace_id: The workspace whose documents are addressed.
            resource: Which kind of document this engine handles.
            record_model: The pydantic model of the sealed record.
            summary_model: The pydantic model of the sealed list summary.
            sleep: The sleep function used between retries; replaced in tests.
        """
        self._transport = transport
        self._keyring_provider = keyring_provider
        self._entropy = entropy
        self._resource = resource
        self._record_model = record_model
        self._summary_model = summary_model
        self._sleep = sleep
        # Parametrized once, so each list row validates *and serializes* as the concrete summary type.
        self._item_model: type[DocumentListItem[SummaryT]] = DocumentListItem[summary_model]  # type: ignore[valid-type]
        self._multi_stream = len(STREAMS_BY_RESOURCE[resource]) > 1
        self._base = f"/api/external/v1/workspaces/{workspace_id}/{resource}"

    # -- paths ---------------------------------------------------------------

    def _stream_path(self, document_id: str) -> str:
        """Return `{base}/{id}` plus `/streams/data` on a multi-stream resource, where versions and drafts live."""
        segment = f"/streams/{DATA_STREAM}" if self._multi_stream else ""
        return f"{self._base}/{document_id}{segment}"

    def _stream_query(self) -> dict[str, str | int | bool] | None:
        """Return `?stream=data` on a multi-stream resource, so that `GET {base}/{id}` answers about the data stream."""
        return {"stream": DATA_STREAM} if self._multi_stream else None

    # -- keys ----------------------------------------------------------------

    def _document_dek(self, index: DocumentIndex, keyring: Keyring | None = None) -> SecretBox:
        """Unwrap the document's DEK with the key of its security group."""
        keyring = keyring or self._keyring_provider()
        group_id = index.security_group_id
        wrapped = index.encrypted_keys.get(group_id)
        if wrapped is None:
            raise CryptoError(
                f"document {index.document_id!r} has no DEK sealed for its own security group {group_id!r}."
            )
        return unwrap_key(keyring.group_key(group_id), wrapped, DOCUMENT_DEK_INFO)

    def _open_summary(self, index: DocumentIndex, dek: SecretBox) -> SummaryT | None:
        """Decrypt `encrypted_index`; return `None` for a document written before the field existed."""
        if index.encrypted_index is None:
            return None
        plaintext = decrypt_content(dek, index.encrypted_index, INDEX_INFO[self._resource])
        return self._summary_model.model_validate_json(plaintext)

    def _seal_summary(self, dek: SecretBox, summary: SummaryT) -> dict[str, str]:
        """Seal `summary` as `encrypted_index`, leaving absent fields out like `JSON.stringify` does."""
        plaintext = summary.model_dump_json(exclude_none=True).encode("utf-8")
        return encrypt_content(dek, plaintext, INDEX_INFO[self._resource]).to_dict()

    def get_index(self, document_id: str) -> DocumentIndex:
        """Fetch the index alone, discarding the `version` and `download` half of `GET {base}/{id}`.

        There is no lighter route for "just the index", so this spends one
        unused presign for callers that only need metadata. It is shared by
        `_Reading` (the public route) and `_Writing.update` (which needs the
        current index before staging a new version).

        Args:
            document_id: The document to look up.

        Returns:
            The document's index.

        Raises:
            NotFoundError: If the document does not exist or is not visible to this account.
        """
        result = self._transport.get(f"{self._base}/{document_id}", query=self._stream_query())
        return DocumentIndex.model_validate(result["document"])
