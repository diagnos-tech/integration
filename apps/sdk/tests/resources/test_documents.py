"""🇺🇸 `VersionedDocuments`: the generic engine, exercised directly against the vault double.

Every assertion about bytes goes through the SDK's own crypto *and* the
double's independent bookkeeping (the object it stored, the size it signed,
the `security_context` it handed out), so a test passes only when the SDK
wrote exactly what the web app would open.

🇧🇷 `VersionedDocuments`: o motor genérico, exercitado direto contra o duplo do cofre.

Toda asserção sobre bytes passa pela cripto do próprio SDK *e* pela
contabilidade independente do duplo (o objeto que guardou, o tamanho que
assinou, o `security_context` que entregou), então um teste só passa quando
o SDK gravou exatamente o que o app web abriria.
"""

from __future__ import annotations

import json

import httpx
import pytest
from diagnos.crypto import (
    DOCUMENT_DEK_INFO,
    INDEX_INFO,
    SEALED_OVERHEAD_BYTES,
    SecretBox,
    decrypt_content,
    derive_content_key,
    open_version_content,
    unwrap_key,
)
from diagnos.crypto.content import DRAFT_CONTENT_INFO, seal_bytes
from diagnos.errors import ConflictError, ProtocolError, VaultError
from diagnos.models import DocumentIndex, ExamRecord, ExamSummary, PatientRecord, PatientSummary
from diagnos.resources._documents import VersionedDocuments
from diagnos.session.keyring import GroupKeyUnavailable

from vault_double import (  # noqa: F401 — `harness` is a fixture, used by name as a parameter
    WORKSPACE_ID,
    Harness,
    harness,
    make_documents,
)

_BASE = f"/api/external/v1/workspaces/{WORKSPACE_ID}"
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


def _seed_patient_draft(h: Harness, index: DocumentIndex, record: PatientRecord) -> None:
    """🇺🇸 Seals `record` as the web editor's autosave would, and stores it as the `data` draft.

    🇧🇷 Sela `record` como o autosave do editor web faria, e o guarda como rascunho de `data`.
    """
    context = h.vault.security_context("patients", index.document_id, "draft:data")["value"]
    key = derive_content_key(_dek(h, index), "draft:data", context)
    sealed = seal_bytes(key, record.model_dump_json(exclude_none=True).encode(), DRAFT_CONTENT_INFO)
    h.vault.seed_draft("patients", index.document_id, sealed)


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


# -- list --------------------------------------------------------------------


def test_list_decrypts_summaries_and_paginates(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 Every row carries its summary; `iter_all` walks every page once.

    🇧🇷 Toda linha traz o resumo; `iter_all` passa uma vez.
    """
    documents = _patients(harness)
    for i in range(5):
        record = PatientRecord(legal_name=f"Patient {i}", display_name=f"P{i}")
        documents.create(record, security_group="sg1", summary=PatientSummary.of(record, []))

    first = documents.list(limit=2)
    names = [item.summary.display_name for item in documents.iter_all(limit=2) if item.summary is not None]

    assert len(first.items) == 2
    assert first.next_cursor is not None
    assert sorted(names) == [f"P{i}" for i in range(5)]
    assert not harness.vault.get_requests  # 🇺🇸/🇧🇷 no version downloaded · nenhuma versão baixada


def test_list_leaves_summary_empty_when_the_group_key_is_missing(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 A row from a group without a key keeps `summary=None` instead of failing the page.

    🇧🇷 Uma linha de um grupo sem chave fica com `summary=None` em vez de derrubar a página.
    """
    documents = _patients(harness)
    documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    documents.create(_JANE, security_group="sg2", summary=PatientSummary.of(_JANE, []))
    del harness.keyring.group_keys["sg2"]

    by_group = {item.index.security_group_id: item.summary for item in documents.list()}

    assert by_group["sg1"] is not None
    assert by_group["sg2"] is None


def test_list_sends_the_filters(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `security_group`/`include_deleted` become the vault's query. 🇧🇷 Os filtros viram a query do cofre."""
    documents = _patients(harness)
    documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))

    page = documents.list(security_group="sg2", include_deleted=True)

    query = harness.vault.api_requests[-1].url.params
    assert query["security_group_id"] == "sg2"
    assert query["include_deleted"] == "true"
    assert page.items == []


# -- update ------------------------------------------------------------------


def test_update_reuses_the_dek_and_carries_the_summary_forward(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 Same DEK, a second version, and the summary callback sees the current summary.

    🇧🇷 Mesma DEK, uma segunda versão, e o callback de resumo vê o resumo atual.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, ["vip"]))
    seen: list[PatientSummary | None] = []
    renamed = _JANE.model_copy(update={"display_name": "Jane D."})

    def summary(current: PatientSummary | None) -> PatientSummary:
        seen.append(current)
        return PatientSummary.of(renamed, current.tags if current else [])

    updated = documents.update(created.index.document_id, renamed, summary=summary)

    assert seen[0] is not None
    assert seen[0].tags == ["vip"]
    assert len(updated.index.versions) == 2
    assert _dek(harness, updated.index) == _dek(harness, created.index)
    assert documents.read(created.index.document_id).summary == PatientSummary.of(renamed, ["vip"])


def test_update_sends_the_conflict_guard_and_surfaces_a_mismatch(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 `expected_latest_version_id` reaches the vault; a stale one is a `ConflictError`.

    🇧🇷 `expected_latest_version_id` chega ao cofre; um desatualizado vira `ConflictError`.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    stale = created.index.latest_version_id
    documents.update(created.index.document_id, _JANE, summary=lambda c: c or PatientSummary())

    with pytest.raises(ConflictError) as raised:
        documents.update(
            created.index.document_id,
            _JANE,
            summary=lambda c: c or PatientSummary(),
            expected_latest_version_id=stale,
        )

    assert raised.value.code == "DocumentVersionMismatch"
    assert _json_bodies(harness, "POST", "/streams/data/versions")[-1]["expected_latest_version_id"] == stale


def test_update_retries_briefly_while_another_writer_holds_the_pending_slot(
    harness: Harness,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🇺🇸 `DocumentVersionPending` is retried (1.5 s, 3 s) like the web app, then surfaced.

    🇧🇷 `DocumentVersionPending` é retentado (1,5 s, 3 s) como o app web, depois exposto.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    document_id = created.index.document_id
    harness.vault.stage_version("patients", document_id, "data", {"content_length": 100})  # 🇺🇸/🇧🇷 another writer

    with pytest.raises(ConflictError) as raised:
        documents.update(document_id, _JANE, summary=lambda c: c or PatientSummary())
    assert raised.value.code == "DocumentVersionPending"
    assert harness.sleeps == [1.5, 3.0]

    harness.sleeps.clear()
    real = harness.vault.stage_version
    calls = {"n": 0}

    def clears_after_one_refusal(*args: object) -> dict[str, object]:
        calls["n"] += 1
        if calls["n"] == 1:
            return real(*args)  # type: ignore[arg-type]
        harness.vault._pending.clear()  # noqa: SLF001 — the other writer's slot expired
        return real(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(harness.vault, "stage_version", clears_after_one_refusal)
    documents.update(document_id, _JANE, summary=lambda c: c or PatientSummary())
    assert harness.sleeps == [1.5]


def test_commit_is_retried_across_server_failures(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 A commit lost to 5xx is replayed with backoff; after three attempts the error surfaces.

    🇧🇷 Um commit perdido em 5xx é reenviado com backoff; depois de três tentativas o erro aparece.
    """
    documents = _patients(harness)
    # 🇺🇸 The transport itself retries a 5xx once, so each engine attempt consumes two failures.
    # 🇧🇷 O transporte já retenta um 5xx uma vez, então cada tentativa do motor consome duas falhas.
    harness.vault.fail_next_commits = 4
    documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    assert harness.sleeps == [0.5, 1.0]

    harness.sleeps.clear()
    harness.vault.fail_next_commits = 6
    with pytest.raises(VaultError) as raised:
        documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    assert raised.value.status == 503
    assert harness.sleeps == [0.5, 1.0]


def test_commit_is_retried_after_a_network_error(
    harness: Harness,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🇺🇸 A dropped connection on commit is replayed; a 4xx is not. 🇧🇷 Conexão caída no commit é reenviada; 4xx não."""
    documents = _patients(harness)
    real = harness.vault.commit_version
    drops = {"left": 1}

    def flaky(*args: object) -> dict[str, object]:
        if drops["left"]:
            drops["left"] -= 1
            raise httpx.ConnectError("connection reset")
        return real(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(harness.vault, "commit_version", flaky)
    documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    assert harness.sleeps == [0.5]


def test_update_refuses_a_patch_only_answer(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """🇺🇸 A version reservation answered as patch-only breaks the contract.

    🇧🇷 Reserva respondida só-patch quebra o contrato.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    monkeypatch.setattr(
        harness.vault,
        "stage_version",
        lambda resource, document_id, _stream, _body: {"staged": False, "document": {}},
    )

    with pytest.raises(ProtocolError):
        documents.update(created.index.document_id, _JANE, summary=lambda c: c or PatientSummary())


# -- flags -------------------------------------------------------------------


def test_flags_are_patch_only(harness: Harness) -> None:  # noqa: F811
    """🇺🇸 Archive/delete send only the flag: no `content_length`, no new version, no upload.

    🇧🇷 Arquivar/apagar mandam só a flag: sem `content_length`, sem versão nova, sem upload.
    """
    documents = _patients(harness)
    created = documents.create(_JANE, security_group="sg1", summary=PatientSummary.of(_JANE, []))
    document_id = created.index.document_id
    uploads = len(harness.vault.put_requests)

    archived = documents.set_flags(document_id, is_archived=True)
    deleted = documents.set_flags(document_id, is_deleted=True)
    restored = documents.set_flags(document_id, is_archived=False, is_deleted=False)

    assert archived.is_archived is True
    assert deleted.is_deleted is True
    assert (restored.is_archived, restored.is_deleted) == (False, False)
    assert len(restored.versions) == 1
    assert len(harness.vault.put_requests) == uploads
    assert _json_bodies(harness, "POST", "/streams/data/versions") == [
        {"is_archived": True},
        {"is_deleted": True},
        {"is_archived": False, "is_deleted": False},
    ]
