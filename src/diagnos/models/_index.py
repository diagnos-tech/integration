"""The vault's index of a document (`docs/PROTOCOL.md §8`): streams, versions, drafts, pagination.

Everything here is what the vault itself reads to route and authorize a
patient, exam or template, and never the clinical content. That content
lives only in a sealed version object (`resources/_documents.py`) or in the
caller's decrypted record (`_patients.py`, `_exams.py`).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from diagnos.crypto import EncryptedPayload

from ._temporal import _instant

ResourceKind = Literal["patients", "exams", "templates"]
StreamName = Literal["data", "file"]

T = TypeVar("T")
SummaryT = TypeVar("SummaryT", bound=BaseModel)


class DocumentVersion(BaseModel):
    """One committed version of a stream (`docs/PROTOCOL.md §8`): metadata only, never content.

    Attributes:
        version_id: The id of the version.
        size: The size of the sealed version object, in bytes.
        created_at: When the version was committed, as an ISO 8601 instant.
        created_by: The account that committed the version.
    """

    model_config = ConfigDict(frozen=True)

    version_id: str
    size: int
    created_at: str
    created_by: str


class DocumentDraft(BaseModel):
    """A stream's mutable draft head: the web editor's autosave, overwritten in place, never a version.

    Attributes:
        rev: The draft revision, which increases with every autosave.
        size: The size of the sealed draft object, in bytes.
        updated_at: When the draft was last saved, as an ISO 8601 instant.
        updated_by: The account that last saved the draft.
    """

    model_config = ConfigDict(frozen=True)

    rev: int
    size: int
    updated_at: str
    updated_by: str


class DocumentStream(BaseModel):
    """One independent line of versions inside a document (`docs/PROTOCOL.md §8`).

    Exams and templates have a single stream, `data`. Patients have two:
    `data` (the structured record this SDK reads and writes) and `file` (the
    web editor's rich document, not exposed by the SDK yet).

    Attributes:
        latest_version_id: The id of the newest committed version, if any.
        versions: Every committed version of the stream.
        pending_version_id: The id of a version reserved but not yet committed, if any.
        draft: The stream's draft head, if one exists.
    """

    model_config = ConfigDict(frozen=True)

    latest_version_id: str | None = None
    versions: list[DocumentVersion] = Field(default_factory=list)
    pending_version_id: str | None = None
    draft: DocumentDraft | None = None

    @property
    def latest_version(self) -> DocumentVersion | None:
        """The entry of `versions` that `latest_version_id` points at, or `None` if there is none."""
        return next((v for v in self.versions if v.version_id == self.latest_version_id), None)

    @property
    def draft_is_newer(self) -> bool:
        """Whether the draft wins under the web app's precedence rule: it exists and is newer than the latest version.

        A commit does not erase the draft, it only supersedes it, so "newer"
        is decided by timestamps: `draft.updated_at` against the latest
        version's `created_at`. An unreadable timestamp never makes the draft
        win, because the committed version is the safe answer.
        """
        if self.draft is None:
            return False
        latest = self.latest_version
        if latest is None:
            return True
        draft_at, latest_at = _instant(self.draft.updated_at), _instant(latest.created_at)
        return draft_at is not None and latest_at is not None and draft_at > latest_at


class DocumentIndex(BaseModel):
    """What the vault knows about a patient, exam or template (`docs/PROTOCOL.md §8`): keys, streams, clear metadata.

    Every field here is something the vault itself reads to route and
    authorize. The clinical content never appears on this model: it lives in
    the sealed object of each version, and a short sealed summary (name or
    title) lives in `encrypted_index`, which only a DEK holder opens.

    Exactly one `security_group_id` per document: sharing a patient with
    another team means copying it, never sharing its key.

    Attributes:
        document_id: The id of the document.
        workspace_id: The workspace that owns the document.
        resource: Which kind of document this is: `patients`, `exams` or `templates`.
        security_group_id: The single security group whose key protects the document.
        encrypted_keys: The document's DEK, wrapped for each security group that may open it.
        encrypted_index: The sealed list and search summary, if the document has one.
        streams: The state of each stream, keyed by stream name.
        meta: Clear (unencrypted) metadata the vault itself reads, such as an exam's `patient_id`.
        created_at: When the document was created, as an ISO 8601 instant.
        created_by: The account that created the document.
        updated_at: When the document last changed, as an ISO 8601 instant.
        updated_by: The account that last changed the document, if known.
        is_archived: Whether the document is archived.
        is_deleted: Whether the document is deleted.
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    workspace_id: str
    resource: ResourceKind
    security_group_id: str
    encrypted_keys: dict[str, EncryptedPayload]
    encrypted_index: EncryptedPayload | None = None
    streams: dict[StreamName, DocumentStream] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    created_by: str
    updated_at: str
    updated_by: str | None = None
    is_archived: bool = False
    is_deleted: bool = False

    @field_validator("meta", mode="before")
    @classmethod
    def _meta_absent_is_empty(cls, value: Any) -> Any:
        """Treat an absent `meta` as empty, because the vault omits it when a document has none."""
        return {} if value is None else value

    def stream(self, name: StreamName = "data") -> DocumentStream:
        """Return one stream's state.

        Args:
            name: The stream to read, `data` by default.

        Returns:
            The stream, or an empty stream when the vault sent none for `name`.
        """
        return self.streams.get(name) or DocumentStream()

    @property
    def latest_version_id(self) -> str | None:
        """Shorthand for `stream("data").latest_version_id`."""
        return self.stream().latest_version_id

    @property
    def versions(self) -> list[DocumentVersion]:
        """Shorthand for `stream("data").versions`."""
        return self.stream().versions

    @property
    def pending_version_id(self) -> str | None:
        """Shorthand for `stream("data").pending_version_id`."""
        return self.stream().pending_version_id


class Page(BaseModel, Generic[T]):
    """One page of a cursor-paginated list (`docs/PROTOCOL.md §8` and `§9`): `items` plus the cursor for the next call.

    `__iter__` yields `items` directly (not pydantic's default field-tuple
    iteration) so that `for item in vault.patients.list(): ...` reads the way
    any Python sequence does. The field-tuple behavior nobody wants here is
    still reachable through `dict(page)` if it were ever needed.

    Attributes:
        items: The rows of this page.
        next_cursor: The cursor to pass to the next call for the following page, or `None` on the last page.
    """

    model_config = ConfigDict(frozen=True)

    items: list[T]
    next_cursor: str | None = None

    def __iter__(self) -> Iterator[T]:  # type: ignore[override]
        """Iterate `items`, not pydantic's default `(field, value)` pairs."""
        return iter(self.items)


class DocumentListItem(BaseModel, Generic[SummaryT]):
    """One row of a list: the index plus its decrypted summary, with no version downloaded.

    `summary` is `None` when the document predates `encrypted_index` or
    belongs to a security group this session holds no key for.

    Attributes:
        index: The vault's index of the document.
        summary: The decrypted summary, or `None` when it cannot be opened.
    """

    model_config = ConfigDict(frozen=True)

    index: DocumentIndex
    summary: SummaryT | None = None

    @property
    def id(self) -> str:
        """Shorthand for `index.document_id`."""
        return self.index.document_id
