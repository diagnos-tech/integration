"""`Exams`: the exam-shaped face of `VersionedDocuments` (`docs/PROTOCOL.md §8`)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from diagnos.dates import TimePrecision, truncate_timestamp
from diagnos.models import DocumentIndex, Exam, ExamListItem, ExamRecord, ExamSummary, Page

from ._documents import DEFAULT_PAGE_SIZE, OpenedDocument, VersionedDocuments, coerce_record
from .patients import require_single_group


class Exams:
    """Exam records: list, read, create, update, archive and unarchive, delete and restore.

    Reached as `vault.exams`. Every record is sealed on the client before upload; the vault only sees
    ciphertext, the security group and a few clear metadata fields such as the exam's patient.
    """

    def __init__(
        self,
        documents: VersionedDocuments[ExamRecord, ExamSummary],
        *,
        time_precision: TimePrecision | None = None,
    ) -> None:
        """Wrap a `VersionedDocuments` for `exams`.

        Args:
            documents: The document engine for the `exams` resource.
            time_precision: If set, dates are truncated to this precision before sealing.
        """
        self._documents = documents
        self._time_precision = time_precision

    def list(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> Page[ExamListItem]:
        """Fetch one page of exams, each with its decrypted summary (title, modality and date).

        Args:
            security_group: Only list exams of this security group.
            include_deleted: Whether to include exams in the trash.
            limit: The page size (the vault caps it at 200).
            cursor: The `next_cursor` of the previous page; `None` for the first page.

        Returns:
            The page of rows and the cursor for the next one. A row whose group key this session does not hold has
            `summary=None`.
        """
        return self._documents.list(
            security_group=security_group, include_deleted=include_deleted, limit=limit, cursor=cursor
        )

    def iter_all(
        self,
        *,
        security_group: str | None = None,
        include_deleted: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[ExamListItem]:
        """Iterate over every exam, across all pages.

        Args:
            security_group: Only list exams of this security group.
            include_deleted: Whether to include exams in the trash.
            limit: The page size used for each request.

        Yields:
            Every matching row, in the order the vault returns them.
        """
        return self._documents.iter_all(security_group=security_group, include_deleted=include_deleted, limit=limit)

    def get(self, exam_id: str, *, version_id: str | None = None, include_draft: bool = True) -> Exam:
        """Fetch and decrypt one exam: the newest content (draft included), or the version `version_id` names.

        Args:
            exam_id: The exam to read.
            version_id: Read this committed version instead of the newest content.
            include_draft: Whether the draft head may win over the latest version. Ignored with `version_id`.

        Returns:
            The exam with its decrypted record and summary.

        Raises:
            NotFoundError: If the exam or version does not exist.
            GroupKeyUnavailable: If this session holds no DEK for the exam's security group.
        """
        return _exam(self._documents.read(exam_id, version_id=version_id, include_draft=include_draft))

    def index(self, exam_id: str) -> DocumentIndex:
        """Fetch the exam's metadata (group, versions, flags, clear `meta`) without opening the record.

        Args:
            exam_id: The exam to look up.

        Returns:
            The vault's index of the exam.

        Raises:
            NotFoundError: If the exam does not exist.
        """
        return self._documents.get_index(exam_id)

    def create(self, record: ExamRecord | Mapping[str, Any], *, patient_id: str, security_group: str) -> Exam:
        """Seal `record`, link it to `patient_id` in clear `meta`, and create the exam.

        `patient_id` is required and clear on purpose: it is the axis the
        vault itself uses to route and authorize an exam without ever
        opening its encrypted content. Everything else, modality included,
        stays sealed.

        Args:
            record: The exam record, or a mapping of its fields. Unknown fields that look like typos are refused.
            patient_id: The patient the exam belongs to.
            security_group: The single security group that will own the exam.

        Returns:
            The created exam.

        Raises:
            TypeError: If `security_group` is not a single group id.
            pydantic.ValidationError: If `record` does not validate.
            GroupKeyUnavailable: If this session holds no DEK for `security_group`.
            VaultError: If the vault rejects the write.
        """
        group = require_single_group(security_group)
        exam_record = self._anonymize(coerce_record(ExamRecord, record))
        opened = self._documents.create(
            exam_record, security_group=group, summary=ExamSummary.of(exam_record), meta={"patient_id": patient_id}
        )
        return _exam(opened)

    def update(
        self,
        exam_id: str,
        record: ExamRecord | Mapping[str, Any],
        *,
        expected_latest_version_id: str | None = None,
    ) -> Exam:
        """Seal a new complete version of `record`; see `Patients.update` for the conflict guard.

        Args:
            exam_id: The exam to update.
            record: The complete new record, or a mapping of its fields.
            expected_latest_version_id: The version you read. If it is no longer the latest, the write is refused.

        Returns:
            The updated exam.

        Raises:
            ConflictError: With `code` `"DocumentVersionMismatch"` when `expected_latest_version_id` is stale.
            NotFoundError: If the exam does not exist.
            pydantic.ValidationError: If `record` does not validate.
            VaultError: If the vault rejects the write.
        """
        exam_record = self._anonymize(coerce_record(ExamRecord, record))
        opened = self._documents.update(
            exam_id,
            exam_record,
            summary=lambda _current: ExamSummary.of(exam_record),
            expected_latest_version_id=expected_latest_version_id,
        )
        return _exam(opened)

    def archive(self, exam_id: str) -> DocumentIndex:
        """Mark the exam archived; this writes no new version.

        Args:
            exam_id: The exam to archive.

        Returns:
            The updated index.
        """
        return self._documents.set_flags(exam_id, is_archived=True)

    def unarchive(self, exam_id: str) -> DocumentIndex:
        """Clear the archived flag; this writes no new version.

        Args:
            exam_id: The exam to unarchive.

        Returns:
            The updated index.
        """
        return self._documents.set_flags(exam_id, is_archived=False)

    def delete(self, exam_id: str) -> DocumentIndex:
        """Move the exam to the trash. This sets a flag and never hard-deletes; `restore` undoes it.

        Args:
            exam_id: The exam to delete.

        Returns:
            The updated index.
        """
        return self._documents.set_flags(exam_id, is_deleted=True)

    def restore(self, exam_id: str) -> DocumentIndex:
        """Take the exam out of the trash.

        Args:
            exam_id: The exam to restore.

        Returns:
            The updated index.
        """
        return self._documents.set_flags(exam_id, is_deleted=False)

    def _anonymize(self, record: ExamRecord) -> ExamRecord:
        """Truncate `exam_date` to `time_precision`, as the web app does before sealing."""
        if self._time_precision is None or record.exam_date is None:
            return record
        return record.model_copy(update={"exam_date": truncate_timestamp(record.exam_date, self._time_precision)})


def _exam(opened: OpenedDocument[ExamRecord, ExamSummary]) -> Exam:
    """Build the public `Exam` for one engine result."""
    return Exam(
        index=opened.index,
        record=opened.record,
        summary=opened.summary,
        version_id=opened.version_id,
        draft_rev=opened.draft_rev,
    )
