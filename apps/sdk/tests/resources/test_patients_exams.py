"""🇺🇸 `Patients`/`Exams`: the resource-specific faces of `VersionedDocuments`.

🇧🇷 `Patients`/`Exams`: as faces específicas de recurso de `VersionedDocuments`.
"""

from __future__ import annotations

from diagnos.models import ExamRecord, PatientRecord
from diagnos.resources.exams import Exams
from diagnos.resources.patients import Patients

from vault_double import (  # noqa: F401 — `harness` is a fixture, used by name as a parameter
    Harness,
    harness,
    make_documents,
)


def _patients(harness: Harness) -> Patients:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 A `Patients` wired to `harness`. 🇧🇷 Um `Patients` conectado a `harness`."""
    return Patients(make_documents(harness, resource="patients", record_model=PatientRecord))


def _exams(harness: Harness) -> Exams:  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
    """🇺🇸 An `Exams` wired to `harness`. 🇧🇷 Um `Exams` conectado a `harness`."""
    return Exams(make_documents(harness, resource="exams", record_model=ExamRecord))


def test_patients_create_accepts_a_plain_dict(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `Patients.create` validates a `dict` into `PatientRecord` — no need to construct the model by hand.

    🇧🇷 `Patients.create` valida um `dict` em `PatientRecord` — sem precisar construir o modelo à mão.
    """
    patients = _patients(harness)

    patient = patients.create({"legal_name": "Jane Doe", "display_name": "Jane"}, security_group="sg1")

    assert isinstance(patient.record, PatientRecord)
    assert patient.record.legal_name == "Jane Doe"
    assert patient.security_groups == ["sg1"]


def test_patients_create_sets_specialist_ids_in_meta(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `specialist_ids` lands in the index's clear `meta`, not inside the encrypted record.

    🇧🇷 `specialist_ids` cai no `meta` em claro do índice, não dentro do registro cifrado.
    """
    patients = _patients(harness)

    patient = patients.create(
        PatientRecord(legal_name="Jane Doe", display_name="Jane"),
        security_group="sg1",
        specialist_ids=["spec_1", "spec_2"],
    )

    assert patient.index.meta["specialist_ids"] == ["spec_1", "spec_2"]


def test_patients_create_accepts_multiple_security_groups(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 A list of groups wraps the DEK once per group, all from the moment of creation.

    🇧🇷 Uma lista de grupos embrulha a DEK uma vez por grupo, já desde a criação.
    """
    patients = _patients(harness)

    patient = patients.create(PatientRecord(legal_name="Jane Doe", display_name="Jane"), security_group=["sg1", "sg2"])

    assert set(patient.security_groups) == {"sg1", "sg2"}
    assert set(patient.index.encrypted_keys.keys()) == {"sg1", "sg2"}


def test_patients_get_returns_a_patient_with_decrypted_record(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `get` decrypts and returns a `Patient` whose `record.legal_name` matches what was created.

    🇧🇷 `get` decifra e devolve um `Patient` cujo `record.legal_name` bate com o que foi criado.
    """
    patients = _patients(harness)
    created = patients.create({"legal_name": "Jane Doe", "display_name": "Jane"}, security_group="sg1")

    fetched = patients.get(created.id)

    assert fetched.record.legal_name == "Jane Doe"
    assert fetched.id == created.id
    assert fetched.updated_at == created.updated_at


def test_patients_update_keeps_the_document_id_and_bumps_the_version(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `update` re-encrypts under a new version but the patient keeps the same `id`.

    🇧🇷 `update` recifra sob uma versão nova mas o paciente mantém o mesmo `id`.
    """
    patients = _patients(harness)
    created = patients.create({"legal_name": "Jane Doe", "display_name": "Jane"}, security_group="sg1")

    updated = patients.update(created.id, {"legal_name": "Jane Doe", "display_name": "Jane D."})

    assert updated.id == created.id
    assert updated.record.display_name == "Jane D."
    assert len(updated.index.versions) == 2


def test_patients_archive_unarchive_delete_flip_the_index_flags(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `archive`/`unarchive`/`delete` each land as a flag on a brand new version of the index.

    🇧🇷 `archive`/`unarchive`/`delete` cada um cai como flag numa versão nova do índice.
    """
    patients = _patients(harness)
    created = patients.create({"legal_name": "Jane Doe", "display_name": "Jane"}, security_group="sg1")

    assert patients.archive(created.id).is_archived is True
    assert patients.unarchive(created.id).is_archived is False
    assert patients.delete(created.id).is_deleted is True


def test_exams_create_links_patient_id_in_meta(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `Exams.create` puts `patient_id`/`modality` in clear `meta`, never inside the encrypted record.

    🇧🇷 `Exams.create` põe `patient_id`/`modality` no `meta` em claro, nunca dentro do registro cifrado.
    """
    exams = _exams(harness)

    exam = exams.create({"title": "Chest CT"}, patient_id="patient_123", security_group="sg1", modality="CT")

    assert isinstance(exam.record, ExamRecord)
    assert exam.record.title == "Chest CT"
    assert exam.index.meta == {"patient_id": "patient_123", "modality": "CT"}
    assert exam.patient_id == "patient_123"


def test_exams_get_returns_the_decrypted_report(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 The exam's `report` content round-trips through creation and `get` intact.

    🇧🇷 O conteúdo de `report` do exame vai e volta intacto por criação e `get`.
    """
    exams = _exams(harness)
    record = ExamRecord(title="Chest CT", report={"format": "text", "content": "unremarkable"})
    created = exams.create(record, patient_id="patient_123", security_group="sg1")

    fetched = exams.get(created.id)

    assert fetched.record.report is not None
    assert fetched.record.report.content == "unremarkable"


def test_exams_list_filters_by_security_group(
    harness: Harness,  # noqa: F811 — pytest fixture shadowing (imported by name), not a real redefinition
) -> None:
    """🇺🇸 `list(security_group=...)` only returns exams that belong to that group.

    🇧🇷 `list(security_group=...)` só devolve exames que pertencem àquele grupo.
    """
    exams = _exams(harness)
    exams.create({"title": "A"}, patient_id="p1", security_group="sg1")
    exams.create({"title": "B"}, patient_id="p1", security_group="sg2")

    page = exams.list(security_group="sg1")

    assert len(page.items) == 1
    assert page.items[0].security_groups == ["sg1"]
