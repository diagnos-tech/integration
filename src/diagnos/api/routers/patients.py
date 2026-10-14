"""`/v1/patients`: a thin HTTP face over `vault.patients` (`apps/sdk/src/diagnos/resources/patients.py`).

Every handler below is a plain `def`, not `async def`. `vault.patients.*` makes blocking HTTP calls to the vault
(`diagnos.transport`), and an `async def` route in FastAPI runs directly on the event loop, so a blocking call there
would stall every other request this process is serving. Starlette runs a sync `def` route in a thread pool instead,
which is the whole reason these stay sync.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from diagnos import Diagnos, DocumentIndex, Page, Patient, PatientListItem
from diagnos.api.deps import get_vault
from diagnos.api.document_params import (
    CURSOR_QUERY_HELP,
    DELETED_QUERY_HELP,
    DRAFT_QUERY_HELP,
    GROUP_QUERY_HELP,
    LIMIT_QUERY_HELP,
    SUMMARY_QUERY_HELP,
    VERSION_QUERY_HELP,
    with_summaries,
)
from diagnos.api.errors import ERROR_RESPONSES
from diagnos.api.mtls import ClientIdentity, require_client_certificate
from diagnos.api.schemas import PatientCreateRequest, PatientUpdateRequest

router = APIRouter(prefix="/v1/patients", tags=["patients"], responses=ERROR_RESPONSES)

PatientId = Annotated[str, Path(description="The patient's document id.")]


@router.get(
    "",
    response_model=Page[PatientListItem],
    summary="List patients",
    description="One page of patients; rows are anonymous unless `summary=true`.",
)
def list_patients(
    security_group: str | None = Query(None, description=GROUP_QUERY_HELP),
    include_deleted: bool = Query(False, description=DELETED_QUERY_HELP),
    limit: int = Query(50, ge=1, le=200, description=LIMIT_QUERY_HELP),
    cursor: str | None = Query(None, description=CURSOR_QUERY_HELP),
    summary: bool = Query(False, description=SUMMARY_QUERY_HELP),
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Page[PatientListItem]:
    """Delegates to `Patients.list`."""
    page = vault.patients.list(
        security_group=security_group, include_deleted=include_deleted, limit=limit, cursor=cursor
    )
    return with_summaries(page, include=summary)


@router.post(
    "",
    response_model=Patient,
    status_code=201,
    summary="Create a patient",
    description="Seals `record` under `security_group` and creates the patient with its first version.",
)
def create_patient(
    body: PatientCreateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Patient:
    """Delegates to `Patients.create`."""
    return vault.patients.create(
        body.record, security_group=body.security_group, tags=body.tags, specialist_ids=body.specialist_ids
    )


@router.get(
    "/{patient_id}",
    response_model=Patient,
    summary="Get one patient",
    description="Fetches and decrypts one patient: the newest content, or `version_id`.",
)
def get_patient(
    patient_id: PatientId,
    version_id: str | None = Query(None, description=VERSION_QUERY_HELP),
    include_draft: bool = Query(True, description=DRAFT_QUERY_HELP),
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Patient:
    """Delegates to `Patients.get`."""
    return vault.patients.get(patient_id, version_id=version_id, include_draft=include_draft)


@router.put(
    "/{patient_id}",
    response_model=Patient,
    summary="Update a patient",
    description="Seals a complete new version of `record`, reusing the patient's DEK.",
)
def update_patient(
    patient_id: PatientId,
    body: PatientUpdateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Patient:
    """Delegates to `Patients.update`."""
    return vault.patients.update(
        patient_id,
        body.record,
        tags=body.tags,
        specialist_ids=body.specialist_ids,
        expected_latest_version_id=body.expected_latest_version_id,
    )


@router.post(
    "/{patient_id}/archive",
    response_model=DocumentIndex,
    summary="Archive a patient",
    description="Sets the archived flag (no new version).",
)
def archive_patient(
    patient_id: PatientId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """Delegates to `Patients.archive`."""
    return vault.patients.archive(patient_id)


@router.post(
    "/{patient_id}/unarchive",
    response_model=DocumentIndex,
    summary="Unarchive a patient",
    description="Clears the archived flag.",
)
def unarchive_patient(
    patient_id: PatientId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """Delegates to `Patients.unarchive`."""
    return vault.patients.unarchive(patient_id)


@router.delete(
    "/{patient_id}",
    response_model=DocumentIndex,
    summary="Move a patient to the trash",
    description="Sets the deleted flag, never a hard delete; `POST .../restore` undoes it.",
)
def delete_patient(
    patient_id: PatientId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """Delegates to `Patients.delete`."""
    return vault.patients.delete(patient_id)


@router.post(
    "/{patient_id}/restore",
    response_model=DocumentIndex,
    summary="Restore a patient from the trash",
    description="Clears the deleted flag.",
)
def restore_patient(
    patient_id: PatientId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """Delegates to `Patients.restore`."""
    return vault.patients.restore(patient_id)
