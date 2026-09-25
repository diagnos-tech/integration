"""🇺🇸 The document models: stream shapes, the draft precedence rule and record validation.

🇧🇷 Os modelos de documento: formas de fluxo, a regra de precedência do rascunho e a validação de registros.
"""

from __future__ import annotations

from typing import Any

import pytest
from diagnos import (
    DocumentIndex,
    DocumentStream,
    Exam,
    ExamRecord,
    Patient,
    PatientRecord,
    PatientSummary,
    PersonalIdentifier,
)
from diagnos.models import vault_context
from pydantic import ValidationError

_SEALED = "secret:v1:c2FsdA:aXY:cGF5bG9hZA"


def _index(**overrides: Any) -> DocumentIndex:
    """🇺🇸 A minimal index as the vault sends it. 🇧🇷 Um índice mínimo como o cofre manda."""
    raw: dict[str, Any] = {
        "document_id": "doc_1",
        "workspace_id": "ws_1",
        "resource": "exams",
        "security_group_id": "sg1",
        "encrypted_keys": {"sg1": {"salt": "s", "nonce": "n", "ciphertext": "c"}},
        "streams": {
            "data": {
                "latest_version_id": "v2",
                "versions": [
                    {"version_id": "v1", "size": 60, "created_at": "2026-09-01T00:00:01.000Z", "created_by": "u"},
                    {"version_id": "v2", "size": 61, "created_at": "2026-09-01T00:00:05.000Z", "created_by": "u"},
                ],
                "pending_version_id": None,
            }
        },
        "meta": None,
        "created_at": "2026-09-01T00:00:01.000Z",
        "created_by": "u",
        "updated_at": "2026-09-01T00:00:05.000Z",
        "is_archived": False,
        "is_deleted": False,
    }
    raw.update(overrides)
    return DocumentIndex.model_validate(raw)


def _with_draft(updated_at: str) -> DocumentStream:
    """🇺🇸 The `data` stream of `_index()` plus a draft. 🇧🇷 O fluxo `data` de `_index()` mais um rascunho."""
    stream = _index().stream()
    draft = {"rev": 3, "size": 70, "updated_at": updated_at, "updated_by": "u"}
    return DocumentStream.model_validate({**stream.model_dump(), "draft": draft})


def test_index_shorthands_read_the_data_stream() -> None:
    """🇺🇸 `latest_version_id`/`versions`/`pending_version_id` come from `streams.data`; `meta: null` is `{}`.

    🇧🇷 `latest_version_id`/`versions`/`pending_version_id` vêm de `streams.data`; `meta: null` é `{}`.
    """
    index = _index()
    assert index.latest_version_id == "v2"
    assert [v.version_id for v in index.versions] == ["v1", "v2"]
    assert index.pending_version_id is None
    assert index.meta == {}
    assert index.stream("file") == DocumentStream()
    assert index.stream().latest_version is not None


@pytest.mark.parametrize(
    ("draft_at", "newer"),
    [
        ("2026-09-01T00:00:06.000Z", True),
        ("2026-09-01T00:00:05.000Z", False),
        ("2026-09-01T00:00:04.000Z", False),
        ("garbage", False),
    ],
)
def test_draft_precedence_follows_the_web_app(draft_at: str, newer: bool) -> None:
    """🇺🇸 The draft wins only when strictly newer; unreadable time never wins.

    🇧🇷 Rascunho só vence se for estritamente mais novo.
    """
    assert _with_draft(draft_at).draft_is_newer is newer


def test_draft_without_any_version_wins_and_no_draft_never_does() -> None:
    """🇺🇸 A draft on an empty stream wins; no draft, no win.

    🇧🇷 Rascunho em fluxo vazio vence; sem rascunho, nada vence.
    """
    draft = {"rev": 1, "size": 1, "updated_at": "x", "updated_by": "u"}
    assert DocumentStream.model_validate({"draft": draft}).draft_is_newer is True
    assert DocumentStream().draft_is_newer is False


def test_identifiers_must_be_vault_sealed_from_the_caller() -> None:
    """🇺🇸 A caller cannot store a plain identity document; the vault's own values pass through.

    🇧🇷 Quem chama não grava documento de identidade em claro; os valores do próprio cofre passam.
    """
    assert PersonalIdentifier(name="cpf", value=_SEALED).value == _SEALED
    with pytest.raises(ValidationError, match="external_id"):
        PatientRecord(legal_name="A", display_name="B", identifiers=[{"name": "cpf", "value": "123.456.789-00"}])
    legacy = PatientRecord.model_validate(
        {"legal_name": "A", "display_name": "B", "identifiers": [{"name": "cpf", "value": "legacy"}]},
        context=vault_context(),
    )
    assert legacy.identifiers is not None


def test_typos_are_refused_and_other_unknown_fields_are_kept() -> None:
    """🇺🇸 A near-miss of a real field fails with the fix; anything else survives, from the caller or the vault.

    🇧🇷 Um quase-acerto de campo real falha com a correção; o resto sobrevive, venha de quem chama ou do cofre.
    """
    with pytest.raises(ValidationError, match="'report_htm' → 'report_html'"):
        ExamRecord(report_htm="<p/>")  # type: ignore[call-arg]
    with pytest.raises(ValidationError, match="pass tags="):
        PatientRecord(legal_name="A", display_name="B", tags=["x"])  # type: ignore[call-arg]
    with pytest.raises(ValidationError, match="patient_id="):
        ExamRecord.model_validate({"patient_id": "p1"})
    kept = PatientRecord(legal_name="A", display_name="B", preferred_language="pt-BR")  # type: ignore[call-arg]
    assert kept.model_extra == {"preferred_language": "pt-BR"}
    record = PatientRecord.model_validate(
        {"legal_name": "A", "display_name": "B", "address": {"city": "Recife", "geo": [1, 2]}, "birthdate": "x"},
        context=vault_context(),
    )
    assert record.model_extra == {"birthdate": "x"}
    assert record.address is not None
    assert record.address.model_extra == {"geo": [1, 2]}


def test_validation_errors_never_echo_the_clinical_value() -> None:
    """🇺🇸 The error names the field, not the value — so it is safe to log. 🇧🇷 O erro nomeia o campo, não o valor."""
    with pytest.raises(ValidationError) as raised:
        PatientRecord(legal_name="Maria da Silva", display_name=42)  # type: ignore[arg-type]
    assert "Maria da Silva" not in str(raised.value)
    assert "display_name" in str(raised.value)


def test_patient_and_exam_shorthands() -> None:
    """🇺🇸 `Patient`/`Exam` expose id, group, draft origin, tags and clear exam meta.

    🇧🇷 `Patient`/`Exam` expõem id, grupo, origem de rascunho, tags e o meta em claro do exame.
    """
    patient = Patient(
        index=_index(resource="patients"),
        record=PatientRecord(legal_name="A", display_name="B"),
        summary=PatientSummary(tags=["vip"]),
        draft_rev=2,
    )
    exam = Exam(index=_index(meta={"patient_id": "p1", "report_status": "published"}), record=ExamRecord())
    bare = Exam(index=_index(), record=ExamRecord())

    assert (patient.id, patient.security_group_id, patient.updated_at) == ("doc_1", "sg1", "2026-09-01T00:00:05.000Z")
    assert patient.from_draft is True
    assert patient.tags == ["vip"]
    assert Patient(index=_index(), record=PatientRecord(legal_name="A", display_name="B")).tags == []
    assert (exam.patient_id, exam.report_status) == ("p1", "published")
    assert (bare.patient_id, bare.report_status) == (None, None)
