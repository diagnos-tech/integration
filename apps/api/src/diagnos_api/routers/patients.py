"""🇺🇸 `/v1/patients` — a thin HTTP face over `vault.patients` (`apps/sdk/src/diagnos/resources/patients.py`).

Every handler below is a plain `def`, not `async def`: `vault.patients.*`
makes blocking HTTP calls to the vault (`diagnos.transport`), and an
`async def` route in FastAPI runs directly on the event loop — a blocking
call there would stall every other request this process is serving.
Starlette runs a sync `def` route in a thread pool instead, which is the
whole reason these stay sync.

🇧🇷 `/v1/patients` — uma face HTTP fina sobre `vault.patients`
(`apps/sdk/src/diagnos/resources/patients.py`).

Todo handler abaixo é um `def` puro, não `async def`: `vault.patients.*` faz
chamadas HTTP bloqueantes ao cofre (`diagnos.transport`), e uma rota
`async def` no FastAPI roda direto no event loop — uma chamada bloqueante
ali travaria toda outra requisição que este processo está servindo. O
Starlette roda uma rota `def` síncrona numa thread pool no lugar, e é essa a
razão inteira destas ficarem síncronas.
"""

from __future__ import annotations

from diagnos import Diagnos, DocumentIndex, Page, Patient, PatientListItem
from fastapi import APIRouter, Depends, Query

from diagnos_api.deps import get_vault
from diagnos_api.document_params import DRAFT_QUERY_HELP, SUMMARY_QUERY_HELP, with_summaries
from diagnos_api.mtls import ClientIdentity, require_client_certificate
from diagnos_api.schemas import PatientCreateRequest, PatientUpdateRequest

router = APIRouter(prefix="/v1/patients", tags=["patients"])


@router.get(
    "",
    response_model=Page[PatientListItem],
    summary="List patients · Lista pacientes",
    description="🇺🇸 One page of patients; rows are anonymous unless `summary=true`. "
    "🇧🇷 Uma página de pacientes; as linhas são anônimas a menos que `summary=true`.",
)
def list_patients(
    security_group: str | None = None,
    include_deleted: bool = False,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    summary: bool = Query(False, description=SUMMARY_QUERY_HELP),
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Page[PatientListItem]:
    """🇺🇸 Delegates to `Patients.list`. 🇧🇷 Delega para `Patients.list`."""
    page = vault.patients.list(
        security_group=security_group, include_deleted=include_deleted, limit=limit, cursor=cursor
    )
    return with_summaries(page, include=summary)


@router.post(
    "",
    response_model=Patient,
    status_code=201,
    summary="Create a patient · Cria um paciente",
    description="🇺🇸 Seals `record` under `security_group` and creates the patient with its first version. "
    "🇧🇷 Sela `record` sob `security_group` e cria o paciente com a primeira versão.",
)
def create_patient(
    body: PatientCreateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Patient:
    """🇺🇸 Delegates to `Patients.create`. 🇧🇷 Delega para `Patients.create`."""
    return vault.patients.create(
        body.record, security_group=body.security_group, tags=body.tags, specialist_ids=body.specialist_ids
    )


@router.get(
    "/{patient_id}",
    response_model=Patient,
    summary="Get one patient · Busca um paciente",
    description="🇺🇸 Fetches and decrypts one patient: the newest content, or `version_id`. "
    "🇧🇷 Busca e decifra um paciente: o conteúdo mais novo, ou `version_id`.",
)
def get_patient(
    patient_id: str,
    version_id: str | None = None,
    include_draft: bool = Query(True, description=DRAFT_QUERY_HELP),
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Patient:
    """🇺🇸 Delegates to `Patients.get`. 🇧🇷 Delega para `Patients.get`."""
    return vault.patients.get(patient_id, version_id=version_id, include_draft=include_draft)


@router.put(
    "/{patient_id}",
    response_model=Patient,
    summary="Update a patient · Atualiza um paciente",
    description="🇺🇸 Seals a complete new version of `record`, reusing the patient's DEK. "
    "🇧🇷 Sela uma versão nova e completa de `record`, reusando a DEK do paciente.",
)
def update_patient(
    patient_id: str,
    body: PatientUpdateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Patient:
    """🇺🇸 Delegates to `Patients.update`. 🇧🇷 Delega para `Patients.update`."""
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
    summary="Archive a patient · Arquiva um paciente",
    description="🇺🇸 Sets the archived flag (no new version). 🇧🇷 Liga a flag de arquivado (sem versão nova).",
)
def archive_patient(
    patient_id: str,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Patients.archive`. 🇧🇷 Delega para `Patients.archive`."""
    return vault.patients.archive(patient_id)


@router.post(
    "/{patient_id}/unarchive",
    response_model=DocumentIndex,
    summary="Unarchive a patient · Desarquiva um paciente",
    description="🇺🇸 Clears the archived flag. 🇧🇷 Tira a flag de arquivado.",
)
def unarchive_patient(
    patient_id: str,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Patients.unarchive`. 🇧🇷 Delega para `Patients.unarchive`."""
    return vault.patients.unarchive(patient_id)


@router.delete(
    "/{patient_id}",
    response_model=DocumentIndex,
    summary="Move a patient to the trash · Manda um paciente para a lixeira",
    description="🇺🇸 Sets the deleted flag — never a hard delete; `POST .../restore` undoes it. "
    "🇧🇷 Liga a flag de apagado — nunca um apagar de verdade; `POST .../restore` desfaz.",
)
def delete_patient(
    patient_id: str,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Patients.delete`. 🇧🇷 Delega para `Patients.delete`."""
    return vault.patients.delete(patient_id)


@router.post(
    "/{patient_id}/restore",
    response_model=DocumentIndex,
    summary="Restore a patient from the trash · Restaura um paciente da lixeira",
    description="🇺🇸 Clears the deleted flag. 🇧🇷 Tira a flag de apagado.",
)
def restore_patient(
    patient_id: str,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Patients.restore`. 🇧🇷 Delega para `Patients.restore`."""
    return vault.patients.restore(patient_id)
