"""🇺🇸 `/v1/exams` — a thin HTTP face over `vault.exams` (`apps/sdk/src/diagnos/resources/exams.py`).

Same reasoning as `routers/patients.py`: every handler is a plain `def`
because `vault.exams.*` blocks on network I/O, and Starlette runs sync
routes in a thread pool instead of the event loop.

🇧🇷 `/v1/exams` — uma face HTTP fina sobre `vault.exams`
(`apps/sdk/src/diagnos/resources/exams.py`).

Mesmo raciocínio de `routers/patients.py`: todo handler é um `def` puro
porque `vault.exams.*` bloqueia em I/O de rede, e o Starlette roda rota
síncrona numa thread pool em vez do event loop.
"""

from __future__ import annotations

from diagnos import Diagnos, DocumentIndex, Exam, Page
from fastapi import APIRouter, Depends

from diagnos_api.deps import get_vault
from diagnos_api.mtls import ClientIdentity, require_client_certificate
from diagnos_api.schemas import ExamCreateRequest, ExamUpdateRequest

router = APIRouter(prefix="/v1/exams", tags=["exams"])


@router.get(
    "",
    response_model=Page[DocumentIndex],
    summary="List exam indexes · Lista índices de exame",
    description="🇺🇸 One page of exam indexes for this workspace; content stays encrypted, see `GET /v1/exams/{id}`. "
    "🇧🇷 Uma página de índices de exame deste workspace; o conteúdo permanece cifrado, veja `GET /v1/exams/{id}`.",
)
def list_exams(
    security_group: str | None = None,
    include_deleted: bool = False,
    limit: int = 50,
    cursor: str | None = None,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Page[DocumentIndex]:
    """🇺🇸 Delegates straight to `Exams.list`. 🇧🇷 Delega direto para `Exams.list`."""
    return vault.exams.list(security_group=security_group, include_deleted=include_deleted, limit=limit, cursor=cursor)


@router.post(
    "",
    response_model=Exam,
    status_code=201,
    summary="Create an exam · Cria um exame",
    description="🇺🇸 Encrypts `record`, links it to `patient_id` in clear metadata, and creates the exam. "
    "🇧🇷 Cifra `record`, liga ao `patient_id` em metadado claro, e cria o exame.",
)
def create_exam(
    body: ExamCreateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Exam:
    """🇺🇸 Delegates to `Exams.create`. 🇧🇷 Delega para `Exams.create`."""
    return vault.exams.create(
        body.record, patient_id=body.patient_id, security_group=body.security_group, modality=body.modality
    )


@router.get(
    "/{exam_id}",
    response_model=Exam,
    summary="Get one exam · Busca um exame",
    description="🇺🇸 Fetches and decrypts one exam, latest version unless `version_id` is given. "
    "🇧🇷 Busca e decifra um exame, na versão mais recente salvo se `version_id` for dado.",
)
def get_exam(
    exam_id: str,
    version_id: str | None = None,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Exam:
    """🇺🇸 Delegates to `Exams.get`. 🇧🇷 Delega para `Exams.get`."""
    return vault.exams.get(exam_id, version_id=version_id)


@router.put(
    "/{exam_id}",
    response_model=Exam,
    summary="Update an exam · Atualiza um exame",
    description="🇺🇸 Encrypts a brand new version of `record`, reusing the exam's existing DEK. "
    "🇧🇷 Cifra uma versão nova de `record`, reusando a DEK existente do exame.",
)
def update_exam(
    exam_id: str,
    body: ExamUpdateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Exam:
    """🇺🇸 Delegates to `Exams.update`. 🇧🇷 Delega para `Exams.update`."""
    return vault.exams.update(exam_id, body.record, modality=body.modality)


@router.post(
    "/{exam_id}/archive",
    response_model=DocumentIndex,
    summary="Archive an exam · Arquiva um exame",
    description="🇺🇸 Marks the exam archived, in a new version. 🇧🇷 Marca o exame arquivado, numa versão nova.",
)
def archive_exam(
    exam_id: str,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Exams.archive`. 🇧🇷 Delega para `Exams.archive`."""
    return vault.exams.archive(exam_id)


@router.post(
    "/{exam_id}/unarchive",
    response_model=DocumentIndex,
    summary="Unarchive an exam · Desarquiva um exame",
    description="🇺🇸 Clears the archived flag, in a new version. 🇧🇷 Tira a flag de arquivado, numa versão nova.",
)
def unarchive_exam(
    exam_id: str,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Exams.unarchive`. 🇧🇷 Delega para `Exams.unarchive`."""
    return vault.exams.unarchive(exam_id)


@router.delete(
    "/{exam_id}",
    response_model=DocumentIndex,
    summary="Delete an exam · Apaga um exame",
    description="🇺🇸 Marks the exam deleted, in a new version — never a hard delete. "
    "🇧🇷 Marca o exame apagado, numa versão nova — nunca um apagar de verdade.",
)
def delete_exam(
    exam_id: str,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Exams.delete`. 🇧🇷 Delega para `Exams.delete`."""
    return vault.exams.delete(exam_id)
