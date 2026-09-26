"""🇺🇸 Shared builders for the `VersionedDocuments` tests: engines, DEK lookup, and request inspection.

Split out of `test_documents.py` so `test_documents.py` (create/paths/read) and
`test_documents_mutations.py` (list/update/flags) share one copy instead of two — bare-imported like
`vault_double`, since both test modules already import `harness` that way.

🇧🇷 Construtores compartilhados dos testes de `VersionedDocuments`: motores, busca de DEK, inspeção de requisição.

Separado de `test_documents.py` para `test_documents.py` (create/paths/read) e
`test_documents_mutations.py` (list/update/flags) compartilharem uma cópia em vez de duas — importado
pelo nome como `vault_double`, já que os dois módulos de teste já importam `harness` desse jeito.
"""

from __future__ import annotations

import json

from diagnos.crypto import DOCUMENT_DEK_INFO, SecretBox, derive_content_key, unwrap_key
from diagnos.crypto.content import DRAFT_CONTENT_INFO, seal_bytes
from diagnos.models import DocumentIndex, ExamRecord, ExamSummary, PatientRecord, PatientSummary
from diagnos.resources._documents import VersionedDocuments

from vault_double import Harness, make_documents  # noqa: F401 — `Harness` is a type used by both test modules

_JANE = PatientRecord(legal_name="Jane Doe", display_name="Jane", external_id="mrn-1")


def _patients(h: Harness) -> VersionedDocuments[PatientRecord, PatientSummary]:
    """🇺🇸 The engine for `patients` (two streams). 🇧🇷 O motor de `patients` (dois fluxos)."""
    return make_documents(h, resource="patients", record_model=PatientRecord, summary_model=PatientSummary)


def _exams(h: Harness) -> VersionedDocuments[ExamRecord, ExamSummary]:
    """🇺🇸 The engine for `exams` (one stream). 🇧🇷 O motor de `exams` (um fluxo)."""
    return make_documents(h, resource="exams", record_model=ExamRecord, summary_model=ExamSummary)


def _dek(h: Harness, index: DocumentIndex) -> SecretBox:
    """🇺🇸 The document DEK, unwrapped independently of the engine. 🇧🇷 A DEK do documento, aberta sem o motor."""
    group_key = h.keyring.group_key(index.security_group_id)
    return unwrap_key(group_key, index.encrypted_keys[index.security_group_id], DOCUMENT_DEK_INFO)


def _json_bodies(h: Harness, method: str, suffix: str) -> list[dict[str, object]]:
    """🇺🇸 The JSON bodies of every API call whose path ends with `suffix`.

    🇧🇷 Os corpos JSON das chamadas com esse sufixo.
    """
    return [
        json.loads(request.content)
        for request in h.vault.api_requests
        if request.method == method and request.url.path.endswith(suffix)
    ]


def _paths(h: Harness) -> list[str]:
    """🇺🇸 `METHOD path` of every API call, in order. 🇧🇷 `MÉTODO path` de toda chamada, em ordem."""
    return [f"{request.method} {request.url.path}" for request in h.vault.api_requests]


def _seed_patient_draft(h: Harness, index: DocumentIndex, record: PatientRecord) -> None:
    """🇺🇸 Seals `record` as the web editor's autosave would, and stores it as the `data` draft.

    🇧🇷 Sela `record` como o autosave do editor web faria, e o guarda como rascunho de `data`.
    """
    context = h.vault.security_context("patients", index.document_id, "draft:data")["value"]
    key = derive_content_key(_dek(h, index), "draft:data", context)
    sealed = seal_bytes(key, record.model_dump_json(exclude_none=True).encode(), DRAFT_CONTENT_INFO)
    h.vault.seed_draft("patients", index.document_id, sealed)
