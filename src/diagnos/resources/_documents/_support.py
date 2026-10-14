"""Shared constants and small free functions the document engine's read and write paths both lean on.

`OpenedDocument` and `coerce_record` are what `resources/patients.py` and
`resources/exams.py` see. The retry and paging budgets and the stream layout
table are read by both `_reading.py` and `_writing.py`. Keeping them here
(rather than duplicated, or hidden as class attributes) means there is
exactly one place that names, say, how many times a `DocumentVersionPending`
reservation is retried.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Generic, TypeVar

import httpx
from pydantic import BaseModel

from diagnos.errors import VaultError
from diagnos.models import DocumentIndex, ResourceKind, StreamName

RecordT = TypeVar("RecordT", bound=BaseModel)
SummaryT = TypeVar("SummaryT", bound=BaseModel)

# §13: list pages cap at 200; 50 mirrors the web app's own default.
DEFAULT_PAGE_SIZE: Final[int] = 50

# Which streams each resource has. This decides the shape of the version URLs: a
# multi-stream resource carries `/streams/{stream}`, a single-stream one does not.
STREAMS_BY_RESOURCE: Final[dict[ResourceKind, tuple[StreamName, ...]]] = {
    "patients": ("data", "file"),
    "exams": ("data",),
    "templates": ("data",),
}

# The structured-record stream: the only one the SDK reads and writes (patients' `file` stream is
# the web editor's binary Lexical/Yjs document, not a record).
DATA_STREAM: Final[StreamName] = "data"

# Same budgets as the web app: a reservation refused because another writer holds the pending
# slot is retried briefly; a commit lost to the network is retried with backoff (it is idempotent).
STAGE_PENDING_ATTEMPTS: Final[int] = 3
STAGE_PENDING_BACKOFF_SECONDS: Final[float] = 1.5
COMMIT_ATTEMPTS: Final[int] = 3
COMMIT_BACKOFF_SECONDS: Final[float] = 0.5

# SSE-C header names the vault lists in `upload.headers`/`client_headers` (see `_put_headers`).
_SSE_C_HEADER_PREFIX: Final[str] = "x-amz-server-side-encryption-customer-"


def coerce_record(model: type[RecordT], value: RecordT | Mapping[str, Any]) -> RecordT:
    """Accept a model instance as is, or validate a plain mapping into one.

    This is the one place where `Patients` and `Exams` let a caller pass
    `{"legal_name": ...}` instead of constructing `PatientRecord(...)` first.
    That gives good REPL ergonomics without weakening validation, since a
    mapping still goes through the same pydantic model (and its unknown-field
    check) either way.

    Args:
        model: The record model to validate against.
        value: A `model` instance, or a mapping of its fields.

    Returns:
        `value` itself if it is already a `model`, otherwise the validated model.

    Raises:
        pydantic.ValidationError: If a mapping does not validate, including an unknown field that looks like a typo.
    """
    return value if isinstance(value, model) else model.model_validate(value)


@dataclass(frozen=True)
class OpenedDocument(Generic[RecordT, SummaryT]):
    """What one read or write returns: the index, the record, its summary, and where the record came from.

    Attributes:
        index: The vault's index of the document.
        record: The decrypted record.
        summary: The decrypted list summary, if any.
        version_id: The committed version the record came from; `None` when it came from the draft head.
        draft_rev: The draft revision the record came from, when it came from the draft head.
    """

    index: DocumentIndex
    record: RecordT
    summary: SummaryT | None
    version_id: str | None
    draft_rev: int | None = None


def _is_retryable_commit_failure(error: Exception) -> bool:
    """Whether a commit can be replayed safely: the network dropped, or the vault failed on its side."""
    if isinstance(error, httpx.TransportError):
        return True
    return isinstance(error, VaultError) and error.status is not None and error.status >= 500
