"""The typed shapes an application actually holds: documents, records, drive nodes, pages.

Everything here is a `pydantic.BaseModel`, deliberately not a hand-rolled
`dataclass`: the SDK's whole external surface is data that just came off the
wire (`model_validate`) or is about to go on it (`model_dump_json`), and
pydantic is what turns "the vault sent a dict" into "either a typed object or
a `ValidationError` that names the exact field" without the SDK writing that
check by hand for every resource. Nothing here ever holds key material. A
`Patient` or `Exam` wraps an already-*decrypted* record, but the DEK that
opened it lives only in the `Keyring` (`session/keyring.py`) and is never a
field on any of these models, so a stray `repr()`, log line or `model_dump()`
of one of these objects can never leak a secret.

This is a package, not a single module, split by domain so that no file grows
past the project's file-size limit. `_shared.py` (the caller-vs-vault
validation rule every sealed record builds on) and `_temporal.py` (date
parsing and writing) are the foundation. `_index.py` is the vault's own
bookkeeping (streams, versions, drafts, pagination). `_patients.py` and
`_exams.py` hold each domain's sealed record and summary. `_opened.py`
composes an index with a decrypted record into `Patient` or `Exam`.
`_drives.py` is the unrelated drive-node domain (`docs/PROTOCOL.md §9`). Every
name a caller could import from `diagnos.models` before this split is
re-exported here unchanged.
"""

from __future__ import annotations

from ._drives import (
    DriveMediaKind,
    DriveNode,
    DriveNodeKind,
    DriveNodeStatus,
    DriveUploadMode,
    OptimizedVariant,
    SecurityContext,
    StagedNode,
)
from ._exams import ExamRecord, ExamSummary
from ._index import (
    DocumentDraft,
    DocumentIndex,
    DocumentListItem,
    DocumentStream,
    DocumentVersion,
    Page,
    ResourceKind,
    StreamName,
    SummaryT,
    T,
)
from ._opened import Exam, Patient
from ._patients import (
    BiologicalSex,
    GenderIdentity,
    PatientAddress,
    PatientRecord,
    PatientSummary,
    PersonalIdentifier,
    RaceIdentity,
)
from ._shared import TYPO_CUTOFF, vault_context
from ._temporal import IsoInstant

# Generic aliases: a list row of one resource, parametrized on its own summary type.
PatientListItem = DocumentListItem[PatientSummary]
"""One row of `vault.patients.list()`: the index plus the decrypted `PatientSummary` (names and tags)."""
ExamListItem = DocumentListItem[ExamSummary]
"""One row of `vault.exams.list()`: the index plus the decrypted `ExamSummary` (title, modality and date)."""

__all__ = [
    "TYPO_CUTOFF",
    "BiologicalSex",
    "DocumentDraft",
    "DocumentIndex",
    "DocumentListItem",
    "DocumentStream",
    "DocumentVersion",
    "DriveMediaKind",
    "DriveNode",
    "DriveNodeKind",
    "DriveNodeStatus",
    "DriveUploadMode",
    "Exam",
    "ExamListItem",
    "ExamRecord",
    "ExamSummary",
    "GenderIdentity",
    "IsoInstant",
    "OptimizedVariant",
    "Page",
    "Patient",
    "PatientAddress",
    "PatientListItem",
    "PatientRecord",
    "PatientSummary",
    "PersonalIdentifier",
    "RaceIdentity",
    "ResourceKind",
    "SecurityContext",
    "StagedNode",
    "StreamName",
    "SummaryT",
    "T",
    "vault_context",
]
