"""🇺🇸 `Patients`/`Exams`: the resource-specific faces of `VersionedDocuments`.

🇧🇷 `Patients`/`Exams`: as faces específicas de recurso de `VersionedDocuments`.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from diagnos.models import ExamRecord, ExamSummary, PatientRecord, PatientSummary
from diagnos.resources.exams import Exams
from diagnos.resources.patients import Patients
from pydantic import ValidationError

from vault_double import (  # noqa: F401 — `harness` is a fixture, used by name as a parameter
    Harness,
    harness,
    make_documents,
)


def _patients(h: Harness, **kwargs: object) -> Patients:
    """🇺🇸 A `Patients` wired to `h`. 🇧🇷 Um `Patients` conectado a `h`."""
    documents = make_documents(h, resource="patients", record_model=PatientRecord, summary_model=PatientSummary)
    return Patients(documents, **kwargs)  # type: ignore[arg-type]


def _exams(h: Harness, **kwargs: object) -> Exams:
    """🇺🇸 An `Exams` wired to `h`. 🇧🇷 Um `Exams` conectado a `h`."""
    documents = make_documents(h, resource="exams", record_model=ExamRecord, summary_model=ExamSummary)
    return Exams(documents, **kwargs)  # type: ignore[arg-type]


def _last_body(h: Harness, suffix: str) -> dict[str, object]:
    """🇺🇸 The JSON body of the last `POST` whose path ends with `suffix`.

    🇧🇷 O corpo do último `POST` com esse sufixo.
    """
    request = next(r for r in reversed(h.vault.api_requests) if r.method == "POST" and r.url.path.endswith(suffix))
    body: dict[str, object] = json.loads(request.content)
    return body


# -- patients ----------------------------------------------------------------


def test_patients_create_accepts_a_plain_dict(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 A `dict` is validated into `PatientRecord`. 🇧🇷 Um `dict` é validado em `PatientRecord`."""
    patient = _patients(harness).create({"legal_name": "Jane Doe", "display_name": "Jane"}, security_group="sg1")

    assert isinstance(patient.record, PatientRecord)
    assert patient.security_group_id == "sg1"
    assert patient.version_id == patient.index.latest_version_id
    assert patient.from_draft is False


def test_patients_create_rejects_a_typo_before_encrypting(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 An unknown field names the closest real one, and nothing reaches the vault.

    🇧🇷 Um campo desconhecido nomeia o real mais próximo, e nada chega ao cofre.
    """
    with pytest.raises(ValidationError, match="'birthdate' → 'birth_date'"):
        _patients(harness).create(
            {"legal_name": "Jane Doe", "display_name": "Jane", "birthdate": "1990-01-01"}, security_group="sg1"
        )
    assert harness.vault.api_requests == []


def test_patients_create_refuses_a_list_of_groups(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 One document, one group — a list explains why. 🇧🇷 Um documento, um grupo — uma lista explica o porquê."""
    with pytest.raises(TypeError, match="exactly one"):
        _patients(harness).create(
            {"legal_name": "Jane Doe", "display_name": "Jane"},
            security_group=["sg1", "sg2"],  # type: ignore[arg-type]
        )


def test_patients_tags_and_specialists(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `tags` are sealed in the summary; `specialist_ids` go to clear `meta`.

    🇧🇷 `tags` ficam seladas no resumo; `specialist_ids` vão para o `meta` em claro.
    """
    patients = _patients(harness)
    patient = patients.create(
        {"legal_name": "Jane Doe", "display_name": "Jane"},
        security_group="sg1",
        tags=["diabetes"],
        specialist_ids=["spec_1"],
    )

    body = _last_body(harness, "/patients")
    assert "tags" not in json.dumps(body["meta"])
    assert body["meta"] == {"specialist_ids": ["spec_1"]}
    assert patient.tags == ["diabetes"]
    assert patients.get(patient.id).tags == ["diabetes"]


def test_patients_update_keeps_tags_unless_given(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `tags=None` carries the current tags forward; a list replaces them.

    🇧🇷 `tags=None` carrega as tags atuais adiante; uma lista as substitui.
    """
    patients = _patients(harness)
    created = patients.create({"legal_name": "Jane Doe", "display_name": "Jane"}, security_group="sg1", tags=["a"])

    kept = patients.update(created.id, {"legal_name": "Jane Doe", "display_name": "Jane D."})
    replaced = patients.update(created.id, kept.record, tags=["b"], specialist_ids=[])

    assert kept.tags == ["a"]
    assert kept.record.display_name == "Jane D."
    assert replaced.tags == ["b"]
    assert _last_body(harness, "/streams/data/versions")["meta"] == {"specialist_ids": []}
    assert len(replaced.index.versions) == 3


def test_patients_update_passes_the_conflict_guard(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `expected_latest_version_id` is forwarded as-is. 🇧🇷 `expected_latest_version_id` é repassado como veio."""
    patients = _patients(harness)
    created = patients.create({"legal_name": "Jane Doe", "display_name": "Jane"}, security_group="sg1")

    patients.update(created.id, created.record, expected_latest_version_id=created.index.latest_version_id)

    body = _last_body(harness, "/streams/data/versions")
    assert body["expected_latest_version_id"] == created.index.latest_version_id


def test_patients_lifecycle_flags(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 archive/unarchive/delete/restore flip the index flags without new versions.

    🇧🇷 archive/unarchive/delete/restore trocam as flags do índice sem versões novas.
    """
    patients = _patients(harness)
    created = patients.create({"legal_name": "Jane Doe", "display_name": "Jane"}, security_group="sg1")

    assert patients.archive(created.id).is_archived is True
    assert patients.unarchive(created.id).is_archived is False
    assert patients.delete(created.id).is_deleted is True
    restored = patients.restore(created.id)
    assert restored.is_deleted is False
    assert len(restored.versions) == 1


def test_patients_list_and_iter_all(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 Rows carry names from the sealed summary. 🇧🇷 As linhas trazem nomes do resumo selado."""
    patients = _patients(harness)
    patients.create({"legal_name": "Jane Doe", "display_name": "Jane"}, security_group="sg1")
    patients.create({"legal_name": "John Roe", "display_name": "John"}, security_group="sg1")

    names = {item.summary.display_name for item in patients.list() if item.summary}
    ids = [item.id for item in patients.iter_all(limit=1)]

    assert names == {"Jane", "John"}
    assert len(ids) == 2


def test_patients_time_precision_truncates_before_sealing(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 With `time_precision="month"`, the stored birth date keeps only year and month.

    🇧🇷 Com `time_precision="month"`, a data de nascimento guardada mantém só ano e mês.
    """
    patients = _patients(harness, time_precision="month")
    created = patients.create(
        {"legal_name": "Jane Doe", "display_name": "Jane", "birth_date": date(1984, 3, 17)}, security_group="sg1"
    )
    updated = patients.update(created.id, created.record.model_copy(update={"birth_date": "1990-07-09"}))

    assert created.record.birth_date == "1984-03-01T00:00:00.000Z"
    assert updated.record.birth_date == "1990-07-01T00:00:00.000Z"
    assert patients.get(created.id).summary.birth_date == "1990-07-01T00:00:00.000Z"  # type: ignore[union-attr]


def test_patients_without_precision_keep_the_date(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 No precision: the date is normalized, not truncated. 🇧🇷 Sem precisão: a data é normalizada, não truncada."""
    patient = _patients(harness).create(
        {"legal_name": "Jane Doe", "display_name": "Jane", "birth_date": "1984-03-17"}, security_group="sg1"
    )
    assert patient.record.birth_date == "1984-03-17T00:00:00.000Z"


# -- exams -------------------------------------------------------------------


def test_exams_create_puts_only_patient_id_in_clear_meta(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `patient_id` is clear; modality and everything else stay sealed, as the web app does.

    🇧🇷 `patient_id` fica em claro; modalidade e todo o resto ficam selados, como o app web faz.
    """
    exam = _exams(harness).create(
        {"title": "Chest CT", "modality": "CT", "exam_date": date(2026, 9, 1)}, patient_id="p1", security_group="sg1"
    )

    assert _last_body(harness, "/exams")["meta"] == {"patient_id": "p1"}
    assert exam.patient_id == "p1"
    assert exam.report_status is None
    assert exam.summary == ExamSummary(title="Chest CT", modality="CT", exam_date="2026-09-01T00:00:00.000Z")


def test_exams_round_trip_the_report(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `report_lexical`/`report_html` come back intact. 🇧🇷 `report_lexical`/`report_html` voltam intactos."""
    exams = _exams(harness)
    record = ExamRecord(title="Chest CT", report_lexical='{"root":{}}', report_html="<p>unremarkable</p>")
    created = exams.create(record, patient_id="p1", security_group="sg1")

    fetched = exams.get(created.id)

    assert fetched.record == record
    assert fetched.index.meta["patient_id"] == "p1"


def test_exams_update_list_and_flags(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 update re-seals the summary; list filters by group; flags are patch-only.

    🇧🇷 update resela o resumo; list filtra por grupo; flags são só-patch.
    """
    exams = _exams(harness, time_precision="day")
    first = exams.create({"title": "A"}, patient_id="p1", security_group="sg1")
    exams.create({"title": "B"}, patient_id="p1", security_group="sg2")

    updated = exams.update(
        first.id, {"title": "A2", "exam_date": "2026-09-01T13:45:00Z"}, expected_latest_version_id=first.version_id
    )
    page = exams.list(security_group="sg1")

    assert updated.summary == ExamSummary(title="A2", exam_date="2026-09-01T00:00:00.000Z")
    assert [item.summary.title for item in page if item.summary] == ["A2"]
    assert len(list(exams.iter_all())) == 2
    assert exams.archive(first.id).is_archived is True
    assert exams.unarchive(first.id).is_archived is False
    assert exams.delete(first.id).is_deleted is True
    assert exams.restore(first.id).is_deleted is False


def test_exams_read_committed_only(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `include_draft=False` and `version_id` are forwarded.

    🇧🇷 `include_draft=False` e `version_id` são repassados.
    """
    exams = _exams(harness)
    created = exams.create({"title": "A"}, patient_id="p1", security_group="sg1")

    pinned = exams.get(created.id, version_id=created.version_id, include_draft=False)

    assert pinned.version_id == created.version_id
    assert pinned.id == created.id
    assert pinned.updated_at == created.updated_at
