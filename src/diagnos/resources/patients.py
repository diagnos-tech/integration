"""`Patients`: the patient-shaped face of `VersionedDocuments` (`docs/PROTOCOL.md §8`)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from diagnos.dates import TimePrecision, truncate_timestamp
from diagnos.models import DocumentIndex, Page, Patient, PatientListItem, PatientRecord, PatientSummary

from ._documents import DEFAULT_PAGE_SIZE, OpenedDocument, VersionedDocuments, coerce_record


def require_single_group(security_group: object) -> str:
    """Return `security_group` if it is one group id; a document belongs to exactly one group, so a list is a mistake.

    Args:
        security_group: The value the caller passed as `security_group`.

    Returns:
        The same id.

    Raises:
        TypeError: If it is not a non-empty `str`, with a message that explains why a list is not accepted.
    """
    if isinstance(security_group, str) and security_group:
        return security_group
    raise TypeError(
        "security_group must be one security group id (a str): a document belongs to exactly one group, and "
        "sharing it with another team means copying it"
    )


class Patients:
    """Patient records: list, read, create, update, archive and unarchive, delete and restore.

    Reached as `vault.patients`. Every record is sealed on the client before upload; the vault only sees
    ciphertext, the security group and a few clear metadata fields.
    """

    def __init__(
        self,
        documents: VersionedDocuments[PatientRecord, PatientSummary],
        *,
        time_precision: TimePrecision | None = None,
    ) -> None:
        """Wrap a `VersionedDocuments` for `patients`.

        Args:
            documents: The document engine for the `patients` resource.
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
    ) -> Page[PatientListItem]:
        """Fetch one page of patients, each with its decrypted summary (names and tags) and no version downloaded.

        Args:
            security_group: Only list patients of this security group.
            include_deleted: Whether to include patients in the trash.
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
    ) -> Iterator[PatientListItem]:
        """Iterate over every patient, across all pages.

        Args:
            security_group: Only list patients of this security group.
            include_deleted: Whether to include patients in the trash.
            limit: The page size used for each request.

        Yields:
            Every matching row, in the order the vault returns them.
        """
        return self._documents.iter_all(security_group=security_group, include_deleted=include_deleted, limit=limit)

    def get(self, patient_id: str, *, version_id: str | None = None, include_draft: bool = True) -> Patient:
        """Fetch and decrypt one patient: the newest content, or the version `version_id` names.

        The newest content is the web app's: its draft head when that is
        newer than the latest version (`Patient.from_draft`), else the
        latest version. Pass `include_draft=False` to read only committed
        versions.

        Args:
            patient_id: The patient to read.
            version_id: Read this committed version instead of the newest content.
            include_draft: Whether the draft head may win over the latest version. Ignored with `version_id`.

        Returns:
            The patient with its decrypted record and summary.

        Raises:
            NotFoundError: If the patient or version does not exist.
            GroupKeyUnavailable: If this session holds no DEK for the patient's security group.
        """
        return _patient(self._documents.read(patient_id, version_id=version_id, include_draft=include_draft))

    def index(self, patient_id: str) -> DocumentIndex:
        """Fetch the patient's metadata (group, versions, flags, sealed summary) without opening the record.

        This is one signed read and no decryption, meant for "which group is
        this patient in?" or "is it archived?", not for reading the record.

        Args:
            patient_id: The patient to look up.

        Returns:
            The vault's index of the patient.

        Raises:
            NotFoundError: If the patient does not exist.
        """
        return self._documents.get_index(patient_id)

    def create(
        self,
        record: PatientRecord | Mapping[str, Any],
        *,
        security_group: str,
        tags: Sequence[str] = (),
        specialist_ids: Sequence[str] | None = None,
    ) -> Patient:
        """Seal `record` under `security_group` and create the patient with its first version.

        Args:
            record: The patient record, or a mapping of its fields. Unknown fields that look like typos are refused.
            security_group: The single security group that will own the patient.
            tags: List and search labels such as `"diabetes"`. They are sealed inside the summary and never sent in
                clear.
            specialist_ids: Ids of the specialists responsible for the patient. They go to clear `meta`, the only
                patient metadata the vault itself reads.

        Returns:
            The created patient.

        Raises:
            TypeError: If `security_group` is not a single group id.
            pydantic.ValidationError: If `record` does not validate.
            GroupKeyUnavailable: If this session holds no DEK for `security_group`.
            VaultError: If the vault rejects the write.
        """
        group = require_single_group(security_group)
        patient_record = self._anonymize(coerce_record(PatientRecord, record))
        meta = {"specialist_ids": list(specialist_ids)} if specialist_ids else None
        opened = self._documents.create(
            patient_record, security_group=group, summary=PatientSummary.of(patient_record, tags), meta=meta
        )
        return _patient(opened)

    def update(
        self,
        patient_id: str,
        record: PatientRecord | Mapping[str, Any],
        *,
        tags: Sequence[str] | None = None,
        specialist_ids: Sequence[str] | None = None,
        expected_latest_version_id: str | None = None,
    ) -> Patient:
        """Seal a new complete version of `record`; `tags=None` keeps the current tags.

        Every version is a complete record, never a delta, so pass the whole
        record. To guard against concurrent edits, pass
        `expected_latest_version_id=patient.index.latest_version_id` from your
        earlier read: the vault then refuses the write if someone else saved
        in between.

        Args:
            patient_id: The patient to update.
            record: The complete new record, or a mapping of its fields.
            tags: The new tags. `None` keeps the current tags.
            specialist_ids: The new specialist ids. `None` leaves them unchanged.
            expected_latest_version_id: The version you read. If it is no longer the latest, the write is refused.

        Returns:
            The updated patient.

        Raises:
            ConflictError: With `code` `"DocumentVersionMismatch"` when `expected_latest_version_id` is stale.
            NotFoundError: If the patient does not exist.
            pydantic.ValidationError: If `record` does not validate.
            VaultError: If the vault rejects the write.
        """
        patient_record = self._anonymize(coerce_record(PatientRecord, record))

        def summary(current: PatientSummary | None) -> PatientSummary:
            """Build the new summary, carrying the current tags when none were given."""
            kept = tags if tags is not None else (current.tags if current is not None else ())
            return PatientSummary.of(patient_record, kept)

        meta = {"specialist_ids": list(specialist_ids)} if specialist_ids is not None else None
        opened = self._documents.update(
            patient_id,
            patient_record,
            summary=summary,
            meta=meta,
            expected_latest_version_id=expected_latest_version_id,
        )
        return _patient(opened)

    def archive(self, patient_id: str) -> DocumentIndex:
        """Mark the patient archived; this writes no new version.

        Args:
            patient_id: The patient to archive.

        Returns:
            The updated index.
        """
        return self._documents.set_flags(patient_id, is_archived=True)

    def unarchive(self, patient_id: str) -> DocumentIndex:
        """Clear the archived flag; this writes no new version.

        Args:
            patient_id: The patient to unarchive.

        Returns:
            The updated index.
        """
        return self._documents.set_flags(patient_id, is_archived=False)

    def delete(self, patient_id: str) -> DocumentIndex:
        """Move the patient to the trash. This sets a flag and never hard-deletes; `restore` undoes it.

        Args:
            patient_id: The patient to delete.

        Returns:
            The updated index.
        """
        return self._documents.set_flags(patient_id, is_deleted=True)

    def restore(self, patient_id: str) -> DocumentIndex:
        """Take the patient out of the trash.

        Args:
            patient_id: The patient to restore.

        Returns:
            The updated index.
        """
        return self._documents.set_flags(patient_id, is_deleted=False)

    def _anonymize(self, record: PatientRecord) -> PatientRecord:
        """Truncate `birth_date` to `time_precision`, as the web app does before sealing."""
        if self._time_precision is None or record.birth_date is None:
            return record
        return record.model_copy(update={"birth_date": truncate_timestamp(record.birth_date, self._time_precision)})


def _patient(opened: OpenedDocument[PatientRecord, PatientSummary]) -> Patient:
    """Build the public `Patient` for one engine result."""
    return Patient(
        index=opened.index,
        record=opened.record,
        summary=opened.summary,
        version_id=opened.version_id,
        draft_rev=opened.draft_rev,
    )
