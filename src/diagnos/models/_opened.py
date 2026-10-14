"""`Patient` and `Exam`: what an application actually holds after opening a document (index, record, summary)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ._exams import ExamRecord, ExamSummary
from ._index import DocumentIndex
from ._patients import PatientRecord, PatientSummary


class _OpenedDocument(BaseModel):
    """Fields shared by `Patient` and `Exam`: the index, where the content came from, and shorthands.

    Attributes:
        index: The vault's index of the document.
        version_id: The committed version the record came from; `None` when it came from the draft head.
        draft_rev: The draft revision the record came from, when the draft was newer.
    """

    model_config = ConfigDict(frozen=True)

    index: DocumentIndex
    version_id: str | None = None
    """The committed version the record came from; `None` when it came from the draft head."""
    draft_rev: int | None = None
    """The draft revision the record came from, when the draft was newer."""

    @property
    def id(self) -> str:
        """The document id, a shorthand for `index.document_id`."""
        return self.index.document_id

    @property
    def updated_at(self) -> str:
        """Shorthand for `index.updated_at`."""
        return self.index.updated_at

    @property
    def security_group_id(self) -> str:
        """Shorthand for `index.security_group_id`."""
        return self.index.security_group_id

    @property
    def from_draft(self) -> bool:
        """Whether the record is the (newer) draft head and not a committed version."""
        return self.draft_rev is not None


class Patient(_OpenedDocument):
    """A patient as an application wants it: the index, the decrypted record and its summary.

    Attributes:
        record: The decrypted patient record.
        summary: The decrypted list summary, or `None` when it cannot be opened.
    """

    record: PatientRecord
    summary: PatientSummary | None = None

    @property
    def tags(self) -> list[str]:
        """The sealed list/search tags (`summary.tags`)."""
        return list(self.summary.tags) if self.summary is not None else []


class Exam(_OpenedDocument):
    """An exam as an application wants it: the index, the decrypted record and its summary.

    Attributes:
        record: The decrypted exam record.
        summary: The decrypted list summary, or `None` when it cannot be opened.
    """

    record: ExamRecord
    summary: ExamSummary | None = None

    @property
    def patient_id(self) -> str | None:
        """The exam's patient, read from clear `meta` (`docs/PROTOCOL.md §8`) and never guessed from content."""
        patient_id = self.index.meta.get("patient_id")
        return str(patient_id) if patient_id is not None else None

    @property
    def report_status(self) -> str | None:
        """`draft` or `published`, from clear `meta`; `None` when never set."""
        status = self.index.meta.get("report_status")
        return str(status) if status is not None else None
