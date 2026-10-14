"""`VersionedDocuments`: the one engine behind patients, exams and templates (`docs/PROTOCOL.md §8`).

`resources/patients.py` and `resources/exams.py` are thin, resource-specific
faces (they know the record type, the summary and the clear `meta`). Every
byte of protocol (paths, keys, sealing, upload, commit) lives here once and
follows the web app step for step, because a document is only useful if
both of them can open it:

- **Keys.** One DEK per document, sealed under the key of the document's
  single security group with `DOCUMENT_DEK_INFO`. Each stored object gets its
  own content key, derived from the DEK and the `security_context` the vault
  hands out next to the signed URL (`crypto/content.py`).
- **Writing** is two-phase: reserve (`POST`, which returns a signed `PUT`
  URL locked to the exact sealed size), `PUT` the sealed bytes, then commit.
  Every version is a complete record, never a delta. The sealed summary
  (`encrypted_index`) travels with the reservation.
- **Reading** follows the web app's precedence rule: the stream's draft head
  (the editor's autosave) wins when it is newer than the latest version.
- **Archive/delete** are patch-only reservations: no new version, no upload.

This is a package, not a single module, so that no file grows past the
project's file-size limit. `_support.py` holds the constants and small free
functions both directions share. `_base.py` is construction, URL shape and
key handling. `_reading.py` and `_writing.py` are the two halves of the
protocol, as mixins that `VersionedDocuments` below stitches together. Every
name importable from `diagnos.resources._documents` before this split is
re-exported here unchanged.
"""

from __future__ import annotations

from ._reading import _Reading
from ._support import _SSE_C_HEADER_PREFIX as _SSE_C_HEADER_PREFIX
from ._support import (
    COMMIT_ATTEMPTS,
    COMMIT_BACKOFF_SECONDS,
    DATA_STREAM,
    DEFAULT_PAGE_SIZE,
    STAGE_PENDING_ATTEMPTS,
    STAGE_PENDING_BACKOFF_SECONDS,
    STREAMS_BY_RESOURCE,
    OpenedDocument,
    RecordT,
    SummaryT,
    coerce_record,
)
from ._support import _is_retryable_commit_failure as _is_retryable_commit_failure
from ._writing import _Writing

__all__ = [
    "COMMIT_ATTEMPTS",
    "COMMIT_BACKOFF_SECONDS",
    "DATA_STREAM",
    "DEFAULT_PAGE_SIZE",
    "STAGE_PENDING_ATTEMPTS",
    "STAGE_PENDING_BACKOFF_SECONDS",
    "STREAMS_BY_RESOURCE",
    "OpenedDocument",
    "VersionedDocuments",
    "coerce_record",
]


class VersionedDocuments(_Reading[RecordT, SummaryT], _Writing[RecordT, SummaryT]):
    """One resource (`patients`, `exams` or `templates`) of one workspace, generic over record and summary types.

    Assembled from `_Reading` and `_Writing` (both built on `_DocumentsBase`
    for construction, URL shape and key handling). Nothing is added here;
    this class exists so that the two halves have one name and one instance.
    """
