"""🇺🇸 `VersionedDocuments`: create, path shape, and read — exercised directly against the vault double.

List/update/flags live in `test_documents_mutations.py`; both share `_documents_common.py`'s engine
builders and request-inspection helpers.

Every assertion about bytes goes through the SDK's own crypto *and* the
double's independent bookkeeping (the object it stored, the size it signed,
the `security_context` it handed out), so a test passes only when the SDK
wrote exactly what the web app would open.

🇧🇷 `VersionedDocuments`: criação, forma do path, e leitura — exercitados direto contra o duplo do cofre.

Listagem/atualização/flags moram em `test_documents_mutations.py`; os dois compartilham os
construtores de motor e os auxiliares de inspeção de requisição de `_documents_common.py`.

Toda asserção sobre bytes passa pela cripto do próprio SDK *e* pela
contabilidade independente do duplo (o objeto que guardou, o tamanho que
assinou, o `security_context` que entregou), então um teste só passa quando
o SDK gravou exatamente o que o app web abriria.
"""

from __future__ import annotations

import json

import pytest
from diagnos.crypto import INDEX_INFO, SEALED_OVERHEAD_BYTES, decrypt_content, open_version_content
from diagnos.errors import ProtocolError
from diagnos.models import ExamRecord, ExamSummary, PatientRecord, PatientSummary
from diagnos.session.keyring import GroupKeyUnavailable

from _documents_common import _JANE, _dek, _exams, _json_bodies, _paths, _patients, _seed_patient_draft
from vault_double import (  # noqa: F401 — `harness` is a fixture, used by name as a parameter
    WORKSPACE_ID,
    Harness,
    harness,
)

_BASE = f"/api/external/v1/workspaces/{WORKSPACE_ID}"

# -- create ------------------------------------------------------------------


def test_create_sends_the_vault_request_body(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 One group, singular id; the DEK sealed for it; the sealed size; the summary; the `data` stream.

    🇧🇷 Um grupo, id no singular; a DEK selada para ele; o tamanho selado; o resumo; o fluxo `data`.
    """
    opened = _patients(harness).create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, ["vip"]))

    (body,) = _json_bodies(harness, "POST", "/patients")
    plaintext = _JANE.model_dump_json(exclude_none=True).encode()
    assert set(body) == {"security_group_id", "encrypted_keys", "content_length", "encrypted_index", "stream"}
    assert body["security_group_id"] == "sg1"
    assert set(body["encrypted_keys"]) == {"sg1"}  # type: ignore[arg-type]
    assert body["content_length"] == len(plaintext) + SEALED_OVERHEAD_BYTES
    assert body["stream"] == "data"
    assert opened.index.security_group_id == "sg1"
    assert opened.version_id == opened.index.latest_version_id


def test_create_stores_what_the_web_app_opens(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 The stored object opens with DEK → content key(version_id, security_context) → raw frame.

    🇧🇷 O objeto guardado abre com DEK → chave de conteúdo(version_id, security_context) → quadro cru.
    """
    opened = _patients(harness).create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))

    version_id = opened.index.latest_version_id
    assert version_id is not None
    sealed = harness.vault._objects[harness.vault.version_url("patients", version_id)]  # noqa: SLF001
    context = harness.vault.security_context("patients", opened.index.document_id, version_id)["value"]
    plaintext = open_version_content(_dek(harness, opened.index), version_id, context, sealed)
    assert PatientRecord.model_validate_json(plaintext) == _JANE
    assert json.loads(plaintext) == json.loads(_JANE.model_dump_json(exclude_none=True))


def test_create_seals_the_summary_as_encrypted_index(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `encrypted_index` opens under the DEK with the patient index label, and carries the tags.

    🇧🇷 O `encrypted_index` abre sob a DEK com o rótulo de índice de paciente, e carrega as tags.
    """
    opened = _patients(harness).create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, ["diabetes"]))

    assert opened.index.encrypted_index is not None
    plaintext = decrypt_content(_dek(harness, opened.index), opened.index.encrypted_index, INDEX_INFO["patients"])
    assert json.loads(plaintext) == {
        "display_name": "Jane",
        "legal_name": "Jane Doe",
        "external_id": "mrn-1",
        "tags": ["diabetes"],
    }


def test_put_sends_the_signed_size_and_never_sse_c(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `content-length` equals the body; no SSE-C header, on the `PUT` or the `GET` (web-app parity).

    🇧🇷 `content-length` igual ao corpo; nenhum header de SSE-C, nem no `PUT` nem no `GET` (paridade com o app web).
    """
    documents = _patients(harness)
    opened = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    documents.read(opened.index.document_id)

    put = harness.vault.put_requests[-1]
    get = harness.vault.get_requests[-1]
    assert put.headers["content-length"] == str(len(put.content))
    for request in (put, get):
        assert not [name for name in request.headers if name.startswith("x-amz-server-side-encryption")]


def test_create_refuses_a_group_this_session_holds_no_key_for(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 Nothing reaches the vault when the group key is missing. 🇧🇷 Nada chega ao cofre sem a chave do grupo."""
    with pytest.raises(GroupKeyUnavailable):
        _patients(harness).create(_JANE, security_group="sg_unknown", summary=PatientSummary.of(_JANE, []))
    assert harness.vault.api_requests == []


def test_a_signed_size_that_does_not_match_is_a_protocol_error(
    harness: Harness,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🇺🇸 The SDK checks the signed size before uploading. 🇧🇷 O SDK confere o tamanho assinado antes do upload."""
    real = harness.vault._signed_upload  # noqa: SLF001

    def lying(url: str, size: int) -> dict[str, object]:
        """🇺🇸 Signs the upload for one byte more than asked, as a lying vault would.

        🇧🇷 Assina o upload para um byte a mais do que o pedido, como um cofre mentiroso faria.
        """
        return real(url, size + 1)

    monkeypatch.setattr(harness.vault, "_signed_upload", lying)
    with pytest.raises(ProtocolError):
        _patients(harness).create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    assert harness.vault.put_requests == []


# -- paths -------------------------------------------------------------------


def test_patients_version_routes_carry_the_stream_segment(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 Patients have two streams, so versions live under `/streams/data`.

    🇧🇷 Pacientes têm dois fluxos: `/streams/data`.
    """
    documents = _patients(harness)
    opened = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    documents.update(opened.index.document_id, _JANE, summary=lambda current: current or PatientSummary())

    document_id = opened.index.document_id
    stream_base = f"{_BASE}/patients/{document_id}/streams/data"
    paths = _paths(harness)
    assert f"POST {stream_base}/versions" in paths
    assert sum(path.startswith(f"POST {stream_base}/versions/") and path.endswith("/commit") for path in paths) == 2
    assert not [path for path in paths if path == f"POST {_BASE}/patients/{document_id}/versions"]


def test_exam_version_routes_have_no_stream_segment(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 Exams have one stream, so the segment does not exist. 🇧🇷 Exames têm um fluxo, então o segmento não existe."""
    documents = _exams(harness)
    record = ExamRecord(title="Chest CT")
    opened = documents.create(record, security_group="sg1", summary=ExamSummary.of(record), meta={"patient_id": "p1"})
    documents.update(opened.index.document_id, record, summary=lambda _current: ExamSummary.of(record))

    document_id = opened.index.document_id
    assert f"POST {_BASE}/exams/{document_id}/versions" in _paths(harness)
    assert not [path for path in _paths(harness) if "/streams/" in path]


# -- read --------------------------------------------------------------------


def test_read_round_trips_the_record_and_summary(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `read` returns the record, the decrypted summary and the version it came from.

    🇧🇷 `read` devolve o registro, o resumo decifrado e a versão de onde veio.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, ["vip"]))

    opened = documents.read(created.index.document_id)

    assert opened.record == _JANE
    assert opened.summary is not None
    assert opened.summary.tags == ["vip"]
    assert opened.version_id == created.index.latest_version_id
    assert opened.draft_rev is None


def test_read_pins_an_older_version(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `version_id` reads history, never the draft. 🇧🇷 `version_id` lê o histórico, nunca o rascunho."""
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    first = created.index.latest_version_id
    documents.update(
        created.index.document_id,
        _JANE.model_copy(update={"display_name": "Jane D."}),
        summary=lambda current: current or PatientSummary(),
    )

    old = documents.read(created.index.document_id, version_id=first)

    assert old.record.display_name == "Jane"
    assert old.version_id == first


def test_read_prefers_a_newer_draft_like_the_web_app(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 A draft newer than the latest version wins; `include_draft=False` reads the committed one.

    🇧🇷 Um rascunho mais novo que a versão corrente vence; `include_draft=False` lê a confirmada.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    _seed_patient_draft(harness, created.index, _JANE.model_copy(update={"display_name": "Jane (typing…)"}))

    newest = documents.read(created.index.document_id)
    committed = documents.read(created.index.document_id, include_draft=False)

    assert newest.record.display_name == "Jane (typing…)"
    assert newest.draft_rev == 1
    assert newest.version_id is None
    assert committed.record.display_name == "Jane"
    assert committed.version_id == created.index.latest_version_id


def test_a_newer_commit_supersedes_the_draft(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 A commit after the draft makes the version win again, without a `GET .../draft`.

    🇧🇷 Um commit depois do rascunho faz a versão vencer de novo, sem `GET .../draft`.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    document_id = created.index.document_id
    _seed_patient_draft(harness, created.index, _JANE.model_copy(update={"display_name": "draft"}))
    documents.update(
        document_id,
        _JANE.model_copy(update={"display_name": "saved"}),
        summary=lambda current: current or PatientSummary(),
    )
    harness.vault.api_requests.clear()

    opened = documents.read(document_id)

    assert opened.record.display_name == "saved"
    assert not [path for path in _paths(harness) if path.endswith("/draft")]


def test_read_keeps_fields_the_sdk_does_not_model(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 A field the web app added survives a read and a `model_copy` round trip.

    🇧🇷 Um campo que o app web acrescentou sobrevive a uma leitura e a um `model_copy`.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    future = PatientRecord.model_construct(**_JANE.model_dump(exclude_none=True), preferred_language="pt-BR")
    _seed_patient_draft(harness, created.index, future)

    opened = documents.read(created.index.document_id)
    rewritten = documents.update(
        created.index.document_id,
        opened.record.model_copy(update={"display_name": "J."}),
        summary=lambda current: current or PatientSummary(),
    )

    assert opened.record.model_extra == {"preferred_language": "pt-BR"}
    assert json.loads(rewritten.record.model_dump_json())["preferred_language"] == "pt-BR"


def test_read_fails_closed_without_the_group_key(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 Losing the group key makes the document unreadable. 🇧🇷 Perder a chave do grupo torna o documento ilegível."""
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    del harness.keyring.group_keys["sg1"]

    with pytest.raises(GroupKeyUnavailable):
        documents.read(created.index.document_id)
