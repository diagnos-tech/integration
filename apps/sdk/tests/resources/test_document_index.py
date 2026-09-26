"""🇺🇸 `Patients.index`/`Exams.index`: a document's metadata without downloading or decrypting its record.

🇧🇷 `Patients.index`/`Exams.index`: o metadado de um documento sem baixar nem decifrar o registro.
"""

from __future__ import annotations

import httpx
from diagnos.models import ExamRecord, ExamSummary, PatientRecord, PatientSummary
from diagnos.resources.exams import Exams
from diagnos.resources.patients import Patients

from vault_double import (  # noqa: F401 — `harness` is a fixture, used by name as a parameter
    Harness,
    harness,
    make_documents,
)


def test_patient_index_reports_the_group_without_touching_storage(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 The group, the latest version and the flags come back; no object is downloaded.

    🇧🇷 O grupo, a versão corrente e as flags voltam; nenhum objeto é baixado.
    """
    documents = make_documents(harness, resource="patients", record_model=PatientRecord, summary_model=PatientSummary)
    patients = Patients(documents)
    created = patients.create({"legal_name": "Jane Doe", "display_name": "Jane"}, security_group="sg1")
    storage_calls: list[str] = []
    real_storage = harness.vault.handle_storage

    def counting(request: httpx.Request) -> httpx.Response:
        """🇺🇸 Records every storage call, then serves it. 🇧🇷 Registra toda chamada ao storage e a atende."""
        storage_calls.append(request.method)
        return real_storage(request)

    harness.transport._storage_client = httpx.Client(transport=httpx.MockTransport(counting))  # noqa: SLF001

    index = patients.index(created.id)

    assert index.security_group_id == "sg1"
    assert index.latest_version_id == created.version_id
    assert index.is_archived is False
    assert storage_calls == []


def test_exam_index_carries_the_clear_patient_link(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 An exam's index exposes `meta.patient_id`, the one field sent in clear.

    🇧🇷 O índice de um exame expõe `meta.patient_id`, o único campo mandado em claro.
    """
    documents = make_documents(harness, resource="exams", record_model=ExamRecord, summary_model=ExamSummary)
    exams = Exams(documents)
    created = exams.create({"title": "CT"}, patient_id="pat_1", security_group="sg1")

    index = exams.index(created.id)

    assert index.meta["patient_id"] == "pat_1"
    assert index.security_group_id == "sg1"
