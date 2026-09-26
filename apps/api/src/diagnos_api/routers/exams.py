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

from typing import Annotated

from diagnos import Diagnos, DocumentIndex, Exam, ExamListItem, Page
from fastapi import APIRouter, Depends, Path, Query

from diagnos_api.deps import get_vault
from diagnos_api.document_params import (
    CURSOR_QUERY_HELP,
    DELETED_QUERY_HELP,
    DRAFT_QUERY_HELP,
    GROUP_QUERY_HELP,
    LIMIT_QUERY_HELP,
    SUMMARY_QUERY_HELP,
    VERSION_QUERY_HELP,
    with_summaries,
)
from diagnos_api.errors import ERROR_RESPONSES
from diagnos_api.mtls import ClientIdentity, require_client_certificate
from diagnos_api.schemas import ExamCreateRequest, ExamUpdateRequest

router = APIRouter(prefix="/v1/exams", tags=["exams"], responses=ERROR_RESPONSES)

ExamId = Annotated[str, Path(description="🇺🇸 The exam's document id. 🇧🇷 O id do documento do exame.")]


@router.get(
    "",
    response_model=Page[ExamListItem],
    summary="🇺🇸 List exams 🇧🇷 Lista exames",
    description="🇺🇸 One page of exams; rows are anonymous unless `summary=true`. "
    "🇧🇷 Uma página de exames; as linhas são anônimas a menos que `summary=true`.",
)
def list_exams(
    security_group: str | None = Query(None, description=GROUP_QUERY_HELP),
    include_deleted: bool = Query(False, description=DELETED_QUERY_HELP),
    limit: int = Query(50, ge=1, le=200, description=LIMIT_QUERY_HELP),
    cursor: str | None = Query(None, description=CURSOR_QUERY_HELP),
    summary: bool = Query(False, description=SUMMARY_QUERY_HELP),
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Page[ExamListItem]:
    """🇺🇸 Delegates to `Exams.list`. 🇧🇷 Delega para `Exams.list`."""
    page = vault.exams.list(security_group=security_group, include_deleted=include_deleted, limit=limit, cursor=cursor)
    return with_summaries(page, include=summary)


@router.post(
    "",
    response_model=Exam,
    status_code=201,
    summary="🇺🇸 Create an exam 🇧🇷 Cria um exame",
    description="🇺🇸 Seals `record`, links it to `patient_id` in clear `meta`, and creates the exam. "
    "🇧🇷 Sela `record`, liga ao `patient_id` no `meta` em claro, e cria o exame.",
)
def create_exam(
    body: ExamCreateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Exam:
    """🇺🇸 Delegates to `Exams.create`. 🇧🇷 Delega para `Exams.create`."""
    return vault.exams.create(body.record, patient_id=body.patient_id, security_group=body.security_group)


@router.get(
    "/{exam_id}",
    response_model=Exam,
    summary="🇺🇸 Get one exam 🇧🇷 Busca um exame",
    description="🇺🇸 Fetches and decrypts one exam: the newest content, or `version_id`. "
    "🇧🇷 Busca e decifra um exame: o conteúdo mais novo, ou `version_id`.",
)
def get_exam(
    exam_id: ExamId,
    version_id: str | None = Query(None, description=VERSION_QUERY_HELP),
    include_draft: bool = Query(True, description=DRAFT_QUERY_HELP),
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Exam:
    """🇺🇸 Delegates to `Exams.get`. 🇧🇷 Delega para `Exams.get`."""
    return vault.exams.get(exam_id, version_id=version_id, include_draft=include_draft)


@router.put(
    "/{exam_id}",
    response_model=Exam,
    summary="🇺🇸 Update an exam 🇧🇷 Atualiza um exame",
    description="🇺🇸 Seals a complete new version of `record`, reusing the exam's DEK. "
    "🇧🇷 Sela uma versão nova e completa de `record`, reusando a DEK do exame.",
)
def update_exam(
    exam_id: ExamId,
    body: ExamUpdateRequest,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> Exam:
    """🇺🇸 Delegates to `Exams.update`. 🇧🇷 Delega para `Exams.update`."""
    return vault.exams.update(exam_id, body.record, expected_latest_version_id=body.expected_latest_version_id)


@router.post(
    "/{exam_id}/archive",
    response_model=DocumentIndex,
    summary="🇺🇸 Archive an exam 🇧🇷 Arquiva um exame",
    description="🇺🇸 Sets the archived flag (no new version). 🇧🇷 Liga a flag de arquivado (sem versão nova).",
)
def archive_exam(
    exam_id: ExamId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Exams.archive`. 🇧🇷 Delega para `Exams.archive`."""
    return vault.exams.archive(exam_id)


@router.post(
    "/{exam_id}/unarchive",
    response_model=DocumentIndex,
    summary="🇺🇸 Unarchive an exam 🇧🇷 Desarquiva um exame",
    description="🇺🇸 Clears the archived flag. 🇧🇷 Tira a flag de arquivado.",
)
def unarchive_exam(
    exam_id: ExamId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Exams.unarchive`. 🇧🇷 Delega para `Exams.unarchive`."""
    return vault.exams.unarchive(exam_id)


@router.delete(
    "/{exam_id}",
    response_model=DocumentIndex,
    summary="🇺🇸 Move an exam to the trash 🇧🇷 Manda um exame para a lixeira",
    description="🇺🇸 Sets the deleted flag — never a hard delete; `POST .../restore` undoes it. "
    "🇧🇷 Liga a flag de apagado — nunca um apagar de verdade; `POST .../restore` desfaz.",
)
def delete_exam(
    exam_id: ExamId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Exams.delete`. 🇧🇷 Delega para `Exams.delete`."""
    return vault.exams.delete(exam_id)


@router.post(
    "/{exam_id}/restore",
    response_model=DocumentIndex,
    summary="🇺🇸 Restore an exam from the trash 🇧🇷 Restaura um exame da lixeira",
    description="🇺🇸 Clears the deleted flag. 🇧🇷 Tira a flag de apagado.",
)
def restore_exam(
    exam_id: ExamId,
    vault: Diagnos = Depends(get_vault),
    _identity: ClientIdentity = Depends(require_client_certificate),
) -> DocumentIndex:
    """🇺🇸 Delegates to `Exams.restore`. 🇧🇷 Delega para `Exams.restore`."""
    return vault.exams.restore(exam_id)
