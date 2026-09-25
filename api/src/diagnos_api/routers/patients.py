"""🇺🇸 `/v1/patients` — a thin HTTP face over `vault.patients` (`sdk/src/diagnos/resources/patients.py`).

Every handler below is a plain `def`, not `async def`: `vault.patients.*`
makes blocking HTTP calls to the vault (`diagnos.transport`), and an
`async def` route in FastAPI runs directly on the event loop — a blocking
call there would stall every other request this process is serving.
Starlette runs a sync `def` route in a thread pool instead, which is the
whole reason these stay sync.

🇧🇷 `/v1/patients` — uma face HTTP fina sobre `vault.patients`
(`sdk/src/diagnos/resources/patients.py`).

Todo handler abaixo é um `def` puro, não `async def`: `vault.patients.*` faz
chamadas HTTP bloqueantes ao cofre (`diagnos.transport`), e uma rota
`async def` no FastAPI roda direto no event loop — uma chamada bloqueante
ali travaria toda outra requisição que este processo está servindo. O
Starlette roda uma rota `def` síncrona numa thread pool no lugar, e é essa a
razão inteira destas ficarem síncronas.
"""

from __future__ import annotations

from diagnos import Diagnos, DocumentIndex, Page, Patient
from fastapi import APIRouter, Depends

from diagnos_api.deps import get_vault
from diagnos_api.mtls import ClientIdentity, require_client_certificate
from diagnos_api.schemas import PatientCreateRequest, PatientUpdateRequest

router = APIRouter(prefix="/v1/patients", tags=["patients"])


@router.get(
    "",
    response_model=Page[DocumentIndex],
    summary="List patient indexes · Lista índices de paciente",
    description="🇺🇸 One page of patient indexes for this workspace; content stays encrypted, see "
    "`GET /v1/patients/{id}`. "
    "🇧🇷 Uma página de índices de paciente deste workspace; o conteúdo permanece cifrado, veja "
    "`GET /v1/patients/{id}`.",
)
def list_patients(
    security_group: str | None = None,
    include_deleted: bool = False,
    limit: int = 50,
    cursor: str | None = None,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Page[DocumentIndex]:
    """🇺🇸 Delegates straight to `Patients.list`. 🇧🇷 Delega direto para `Patients.list`."""
    return vault.patients.list(
        security_group=security_group, include_deleted=include_deleted, limit=limit, cursor=cursor
    )


@router.post(
    "",
    response_model=Patient,
    status_code=201,
    summary="Create a patient · Cria um paciente",
    description="🇺🇸 Encrypts `record` under `security_group` and creates the patient. "
    "🇧🇷 Cifra `record` sob `security_group` e cria o paciente.",
)
def create_patient(
    body: PatientCreateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Patient:
    """🇺🇸 Delegates to `Patients.create`. 🇧🇷 Delega para `Patients.create`."""
    return vault.patients.create(body.record, security_group=body.security_group, specialist_ids=body.specialist_ids)


@router.get(
    "/{patient_id}",
    response_model=Patient,
    summary="Get one patient · Busca um paciente",
    description="🇺🇸 Fetches and decrypts one patient, latest version unless `version_id` is given. "
    "🇧🇷 Busca e decifra um paciente, na versão mais recente salvo se `version_id` for dado.",
)
def get_patient(
    patient_id: str,
    version_id: str | None = None,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Patient:
    """🇺🇸 Delegates to `Patients.get`. 🇧🇷 Delega para `Patients.get`."""
    return vault.patients.get(patient_id, version_id=version_id)


@router.put(
    "/{patient_id}",
    response_model=Patient,
    summary="Update a patient · Atualiza um paciente",
    description="🇺🇸 Encrypts a brand new version of `record`, reusing the patient's existing DEK. "
    "🇧🇷 Cifra uma versão nova de `record`, reusando a DEK existente do paciente.",
)
def update_patient(
    patient_id: str,
    body: PatientUpdateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Patient:
    """🇺🇸 Delegates to `Patients.update`. 🇧🇷 Delega para `Patients.update`."""
    return vault.patients.update(patient_id, body.record)


@router.post(
    "/{patient_id}/archive",
    response_model=DocumentIndex,
    summary="Archive a patient · Arquiva um paciente",
    description="🇺🇸 Marks the patient archived, in a new version. 🇧🇷 Marca o paciente arquivado, numa versão nova.",
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
    description="🇺🇸 Clears the archived flag, in a new version. 🇧🇷 Tira a flag de arquivado, numa versão nova.",
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
    summary="Delete a patient · Apaga um paciente",
    description="🇺🇸 Marks the patient deleted, in a new version — never a hard delete. "
    "🇧🇷 Marca o paciente apagado, numa versão nova — nunca um apagar de verdade.",
)
def delete_patient(
    patient_id: str,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Patients.delete`. 🇧🇷 Delega para `Patients.delete`."""
    return vault.patients.delete(patient_id)
