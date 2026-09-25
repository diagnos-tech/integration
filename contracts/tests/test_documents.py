"""🇺🇸 Versioned documents (`docs/PROTOCOL.md §8`): what the SDK asks of `/patients` and `/exams`, and reads back.

Each test drives the SDK's real `Patients`/`Exams` against the Pact mock:
reserve → `PUT` → commit, open the latest version, prefer a newer draft,
reserve the next version under a conflict guard, flip a flag without a new
version, list, and back off on a pending version. The object bodies the SDK
downloads are sealed here by an independent implementation (`_crypto.py`,
`cryptography`), following the web app's composition — DEK wrapped with
`imgexam-patient-dek-v1`, per-object key `HKDF(dek, salt=version_id,
info=security_context)`, raw `salt ‖ nonce ‖ ciphertext` — so a green run is
also proof that the SDK opens what the web app writes.

Object storage (the presigned `PUT`/`GET`) is not the vault's API and not
part of the contract: `make_transport(storage=...)` stubs it in memory.

🇧🇷 Documentos versionados (`docs/PROTOCOL.md §8`): o que o SDK pede a `/patients` e `/exams`, e o que lê de volta.

Cada teste conduz os `Patients`/`Exams` de verdade do SDK contra o mock do
Pact: reservar → `PUT` → confirmar, abrir a versão corrente, preferir um
rascunho mais novo, reservar a próxima versão sob trava de conflito, trocar
uma flag sem versão nova, listar, e recuar diante de uma versão pendente. Os
corpos de objeto que o SDK baixa são selados aqui por uma implementação
independente (`_crypto.py`, `cryptography`), seguindo a composição do app
web — DEK embrulhada com `imgexam-patient-dek-v1`, chave por objeto
`HKDF(dek, salt=version_id, info=security_context)`, `salt ‖ nonce ‖
ciphertext` cru — então uma rodada verde também prova que o SDK abre o que o
app web grava.

O armazenamento de objetos (o `PUT`/`GET` pré-assinado) não é a API do cofre
nem parte do contrato: `make_transport(storage=...)` o substitui em memória.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from diagnos import ConflictError, ExamRecord, ExamSummary, PatientRecord, PatientSummary
from diagnos.crypto import EntropyMixer
from diagnos.crypto.secure import SecretBox
from diagnos.models import ResourceKind
from diagnos.resources._documents import VersionedDocuments
from diagnos.resources.exams import Exams
from diagnos.resources.patients import Patients
from diagnos.session.keyring import Keyring
from pact import Pact, match
from pydantic import BaseModel

from _crypto import (
    DOCUMENT_DEK_INFO,
    DRAFT_CONTENT_INFO,
    INDEX_INFO,
    VERSION_CONTENT_INFO,
    b64url,
    content_key,
    fixed_bytes,
    seal_body,
    seal_content,
)
from _wire import (
    ACCOUNT_ID,
    B64URL,
    EXTERNAL_PREFIX,
    HTTPS_URL,
    SECURITY_GROUP_ID,
    WORKSPACE_ID,
    declare_clock,
    encrypted,
    failure,
    instant,
    literal,
    ok,
    path,
    session_keys,
    signed_headers,
    workspace_state,
)
from conftest import make_transport

GROUP_KEY = fixed_bytes("group/dek")
DEK = fixed_bytes("document/dek")
PATIENT_ID = "pat-contract"
EXAM_ID = "exam-contract"
VERSION_1 = "ver-contract-1"
VERSION_2 = "ver-contract-2"
CONTEXT = b64url(fixed_bytes("document/security-context"))
DRAFT_CONTEXT = b64url(fixed_bytes("document/draft-context"))
CREATED_AT = "2026-09-01T12:00:00.000Z"
DRAFT_AT = "2026-09-01T12:05:00.000Z"
UPLOAD_URL = "https://objects.diagnos.test/upload?X-Amz-Signature=contract"
DOWNLOAD_URL = "https://objects.diagnos.test/download?X-Amz-Signature=contract"
DRAFT_URL = "https://objects.diagnos.test/draft?X-Amz-Signature=contract"

MARIA = PatientRecord(legal_name="Maria da Silva", display_name="Maria", birth_date="1984-03-02")
MARIA_DRAFT = MARIA.model_copy(update={"display_name": "Maria (rascunho)"})
MARIA_SUMMARY = PatientSummary.of(MARIA, ["diabetes"])
SCAN = ExamRecord(title="RM de crânio", modality="MR", exam_date="2026-09-01")
SCAN_SUMMARY = ExamSummary.of(SCAN)

_WS = rf"^{EXTERNAL_PREFIX}/workspaces/[^/]+"
_WS_EXPR = f"{EXTERNAL_PREFIX}/workspaces/${{workspace_id}}"
_BASE = f"{EXTERNAL_PREFIX}/workspaces/{WORKSPACE_ID}"


def _sealed_length(record: BaseModel) -> int:
    """🇺🇸 `content_length` the SDK declares: the JSON record plus 44 bytes of framing and tag.

    🇧🇷 O `content_length` que o SDK declara: o registro JSON mais 44 bytes de enquadramento e tag.
    """
    return len(record.model_dump_json(exclude_none=True).encode("utf-8")) + 44


def _summary_payload(resource: str, summary: BaseModel) -> dict[str, str]:
    """🇺🇸 A real `encrypted_index` under the fixed document DEK. 🇧🇷 Um `encrypted_index` real sob a DEK fixa."""
    plaintext = summary.model_dump_json(exclude_none=True).encode("utf-8")
    return seal_content(DEK, plaintext, INDEX_INFO[resource], label=f"{resource}/index")


def _index(
    document_id: str,
    *,
    resource: str,
    summary: BaseModel,
    stream: dict[str, object],
    meta: dict[str, object] | None = None,
    is_archived: bool = False,
) -> dict[str, object]:
    """🇺🇸 `documentIndexResponse` as the SDK reads it: keys, the sealed summary, the `data` stream, flags.

    🇧🇷 `documentIndexResponse` como o SDK o lê: chaves, o resumo selado, o fluxo `data`, flags.
    """
    wrapped = seal_content(GROUP_KEY, DEK, DOCUMENT_DEK_INFO, label="document/wrapped-dek")
    body: dict[str, object] = {
        "document_id": match.str(document_id),
        "workspace_id": match.str(WORKSPACE_ID),
        "resource": literal(resource),
        "security_group_id": match.str(SECURITY_GROUP_ID),
        "encrypted_keys": match.each_value_matches(
            {SECURITY_GROUP_ID: wrapped}, rules=match.like({"salt": "s", "nonce": "n", "ciphertext": "c"})
        ),
        "encrypted_index": encrypted(_summary_payload(resource, summary)),
        "streams": {"data": stream},
        "created_at": instant(CREATED_AT),
        "created_by": match.str(ACCOUNT_ID),
        "updated_at": instant(CREATED_AT),
        "is_archived": match.bool(is_archived),
        "is_deleted": match.bool(False),
    }
    if meta is not None:
        body["meta"] = meta
    return body


def _stream(*, size: int, pending: str | None = None, draft: dict[str, object] | None = None) -> dict[str, object]:
    """🇺🇸 One committed version (`VERSION_1`), optionally a pending id and a draft head.

    🇧🇷 Uma versão confirmada (`VERSION_1`), opcionalmente um id pendente e uma cabeça de rascunho.
    """
    stream: dict[str, object] = {
        "latest_version_id": match.str(VERSION_1),
        "versions": match.each_like(
            {
                "version_id": match.str(VERSION_1),
                "size": match.int(size),
                "created_at": instant(CREATED_AT),
                "created_by": match.str(ACCOUNT_ID),
            }
        ),
        "pending_version_id": match.str(pending) if pending is not None else None,
    }
    if draft is not None:
        stream["draft"] = draft
    return stream


def _reservation(version_id: str, size: int) -> dict[str, object]:
    """🇺🇸 What a reservation answers that the SDK uses: the version id, its context, the signed `PUT`.

    🇧🇷 O que uma reserva responde e o SDK usa: o id da versão, o contexto dela, o `PUT` assinado.
    """
    return {
        "version_id": match.str(version_id),
        "security_context": {"value": match.regex(CONTEXT, regex=B64URL)},
        "upload": {
            "url": match.regex(UPLOAD_URL, regex=HTTPS_URL),
            "headers": {"content-length": match.regex(str(size), regex=r"^[1-9][0-9]*$")},
        },
    }


def _keyring() -> Keyring:
    """🇺🇸 The session plus the one group key the approval in `test_session.py` hands out.

    🇧🇷 A sessão mais a chave de grupo que a aprovação de `test_session.py` entrega.
    """
    return Keyring(
        enrollment_id="enr-contract",
        session=session_keys(),
        group_keys={SECURITY_GROUP_ID: SecretBox.from_bytes(bytearray(GROUP_KEY))},
    )


class _Storage:
    """🇺🇸 In-memory R2: serves fixed objects by URL and records every `PUT`.

    🇧🇷 R2 em memória: serve objetos fixos por URL e registra todo `PUT`.
    """

    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        """🇺🇸 `objects` maps a download URL to its body. 🇧🇷 `objects` mapeia uma URL de download ao corpo."""
        self.objects = dict(objects or {})
        self.puts: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        """🇺🇸 The `httpx.MockTransport` handler. 🇧🇷 O handler do `httpx.MockTransport`."""
        if request.method == "PUT":
            self.puts.append(request)
            return httpx.Response(200)
        body = self.objects.get(str(request.url))
        return httpx.Response(200, content=body) if body is not None else httpx.Response(404)


def _engine(
    url: str, resource: ResourceKind, record: type[Any], summary: type[Any], storage: _Storage
) -> VersionedDocuments[Any, Any]:
    """🇺🇸 The SDK's real engine over the mock server, with the contract keyring. 🇧🇷 O motor real do SDK sobre o mock."""
    return VersionedDocuments(
        make_transport(url, storage=storage),
        _keyring,
        EntropyMixer(),
        workspace_id=WORKSPACE_ID,
        resource=resource,
        record_model=record,
        summary_model=summary,
        sleep=lambda seconds: None,
    )


def _patients(url: str, storage: _Storage) -> Patients:
    """🇺🇸 `vault.patients` over the mock server. 🇧🇷 `vault.patients` sobre o mock."""
    return Patients(_engine(url, "patients", PatientRecord, PatientSummary, storage))


def _exams(url: str, storage: _Storage) -> Exams:
    """🇺🇸 `vault.exams` over the mock server. 🇧🇷 `vault.exams` sobre o mock."""
    return Exams(_engine(url, "exams", ExamRecord, ExamSummary, storage))


def _sealed_version(record: BaseModel, *, label: str) -> bytes:
    """🇺🇸 `VERSION_1`'s object body, sealed by the oracle. 🇧🇷 O corpo do objeto de `VERSION_1`, selado pelo oráculo."""
    key = content_key(DEK, VERSION_1, CONTEXT)
    return seal_body(key, record.model_dump_json(exclude_none=True).encode("utf-8"), VERSION_CONTENT_INFO, label=label)


# -- interactions --------------------------------------------------------------

_PATIENTS = (f"{_BASE}/patients", rf"{_WS}/patients$", f"{_WS_EXPR}/patients")
_EXAMS = (f"{_BASE}/exams", rf"{_WS}/exams$", f"{_WS_EXPR}/exams")


def _patient_path(suffix: str = "") -> Any:
    """🇺🇸 `.../patients/{document_id}{suffix}`, rebuilt from provider state at verification.

    🇧🇷 `.../patients/{document_id}{suffix}`, remontado a partir do provider state na verificação.
    """
    return path(
        f"{_BASE}/patients/{PATIENT_ID}{suffix}",
        pattern=rf"{_WS}/patients/[^/]+{suffix}$",
        expression=f"{_WS_EXPR}/patients/${{document_id}}{suffix}",
    )


def _declare_open_patient(pact: Pact, *, state: str, description: str, stream: dict[str, object]) -> None:
    """🇺🇸 `GET .../patients/{id}?stream=data` under `state`, answering the index plus the latest version.

    🇧🇷 `GET .../patients/{id}?stream=data` sob `state`, respondendo o índice mais a versão corrente.
    """
    name, params = workspace_state(state, document_id=PATIENT_ID, security_group_id=SECURITY_GROUP_ID)
    (
        pact.upon_receiving(description)
        .given(name, params)
        .with_request("GET", _patient_path())
        .with_query_parameter("stream", "data")
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body(
            ok(
                {
                    "document": _index(PATIENT_ID, resource="patients", summary=MARIA_SUMMARY, stream=stream),
                    "version": {"version_id": match.str(VERSION_1)},
                    "security_context": {"value": match.regex(CONTEXT, regex=B64URL)},
                    "download": {"url": match.regex(DOWNLOAD_URL, regex=HTTPS_URL)},
                }
            ),
            content_type="application/json",
        )
    )


def _declare_commit(
    pact: Pact, *, resource: str, document_id: str, version_id: str, description: str, stream: dict[str, object]
) -> None:
    """🇺🇸 `POST .../versions/{version_id}/commit` — with `/streams/data` on patients only.

    🇧🇷 `POST .../versions/{version_id}/commit` — com `/streams/data` só em pacientes.
    """
    segment = "/streams/data" if resource == "patients" else ""
    summary = MARIA_SUMMARY if resource == "patients" else SCAN_SUMMARY
    meta: dict[str, object] | None = None if resource == "patients" else {"patient_id": match.str(PATIENT_ID)}
    name, params = workspace_state(
        f"{'a patient' if resource == 'patients' else 'an exam'} has an uploaded version waiting to be committed",
        document_id=document_id,
        version_id=version_id,
        security_group_id=SECURITY_GROUP_ID,
    )
    request_path = path(
        f"{_BASE}/{resource}/{document_id}{segment}/versions/{version_id}/commit",
        pattern=rf"{_WS}/{resource}/[^/]+{segment}/versions/[^/]+/commit$",
        expression=f"{_WS_EXPR}/{resource}/${{document_id}}{segment}/versions/${{version_id}}/commit",
    )
    (
        pact.upon_receiving(description)
        .given(name, params)
        .with_request("POST", request_path)
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body(
            ok({"document": _index(document_id, resource=resource, summary=summary, stream=stream, meta=meta)}),
            content_type="application/json",
        )
    )


# -- patients ------------------------------------------------------------------


def test_create_patient_reserves_uploads_and_commits_the_first_version(pact: Pact) -> None:
    """🇺🇸 One group, the DEK sealed for it, the sealed size, the sealed summary → `PUT` → commit.

    🇧🇷 Um grupo, a DEK selada para ele, o tamanho selado, o resumo selado → `PUT` → commit.
    """
    size = _sealed_length(MARIA)
    wrapped = seal_content(GROUP_KEY, DEK, DOCUMENT_DEK_INFO, label="document/wrapped-dek")
    declare_clock(pact)
    name, params = workspace_state(
        "the SDK session holds the key of a security group", security_group_id=SECURITY_GROUP_ID
    )
    (
        pact.upon_receiving("an SDK process creates a patient and reserves its first version")
        .given(name, params)
        .with_request("POST", path(_PATIENTS[0], pattern=_PATIENTS[1], expression=_PATIENTS[2]))
        .with_headers(signed_headers())
        .with_body(
            {
                "security_group_id": literal(SECURITY_GROUP_ID),
                "encrypted_keys": {SECURITY_GROUP_ID: encrypted(wrapped)},
                "content_length": match.int(size),
                "encrypted_index": encrypted(_summary_payload("patients", MARIA_SUMMARY)),
                "stream": literal("data"),
            },
            content_type="application/json",
        )
        .will_respond_with(201)
        .with_body(
            ok({"document": {"document_id": match.str(PATIENT_ID)}, **_reservation(VERSION_1, size)}),
            content_type="application/json",
        )
    )
    _declare_commit(
        pact,
        resource="patients",
        document_id=PATIENT_ID,
        version_id=VERSION_1,
        description="an SDK process commits the first version of a patient",
        stream=_stream(size=size),
    )
    storage = _Storage()

    with pact.serve() as server:
        patient = _patients(str(server.url), storage).create(MARIA, security_group=SECURITY_GROUP_ID, tags=["diabetes"])

    (put,) = storage.puts
    assert str(put.url) == UPLOAD_URL
    assert len(put.content) == size
    assert patient.id == PATIENT_ID
    assert patient.version_id == VERSION_1
    assert patient.tags == ["diabetes"]


def test_open_patient_decrypts_what_the_web_app_sealed(pact: Pact) -> None:
    """🇺🇸 Index → DEK (group key) → content key (version, context) → the record; the summary opens too.

    🇧🇷 Índice → DEK (chave do grupo) → chave de conteúdo (versão, contexto) → o registro; o resumo abre também.
    """
    declare_clock(pact)
    _declare_open_patient(
        pact,
        state="a patient has one committed version",
        description="an SDK process opens the latest version of a patient",
        stream=_stream(size=_sealed_length(MARIA)),
    )
    storage = _Storage({DOWNLOAD_URL: _sealed_version(MARIA, label="patient/v1")})

    with pact.serve() as server:
        patient = _patients(str(server.url), storage).get(PATIENT_ID)

    assert patient.record == MARIA
    assert patient.version_id == VERSION_1
    assert patient.from_draft is False
    assert patient.summary == MARIA_SUMMARY


def test_open_patient_prefers_a_newer_draft(pact: Pact) -> None:
    """🇺🇸 A draft newer than the latest version wins, as in the web app: `GET .../draft`, then its object.

    🇧🇷 Um rascunho mais novo que a versão corrente vence, como no app web: `GET .../draft`, depois o objeto.
    """
    draft_plaintext = MARIA_DRAFT.model_dump_json(exclude_none=True).encode("utf-8")
    draft_body = seal_body(
        content_key(DEK, "draft:data", DRAFT_CONTEXT), draft_plaintext, DRAFT_CONTENT_INFO, label="patient/draft"
    )
    state = "a patient has a draft newer than its latest version"
    declare_clock(pact)
    _declare_open_patient(
        pact,
        state=state,
        description="an SDK process opens a patient whose draft is newer than its latest version",
        stream=_stream(
            size=_sealed_length(MARIA),
            draft={
                "rev": match.int(1),
                "size": match.int(len(draft_body)),
                "updated_at": instant(DRAFT_AT),
                "updated_by": match.str(ACCOUNT_ID),
            },
        ),
    )
    name, params = workspace_state(state, document_id=PATIENT_ID, security_group_id=SECURITY_GROUP_ID)
    (
        pact.upon_receiving("an SDK process resolves the draft head of a patient's data stream")
        .given(name, params)
        .with_request("GET", _patient_path("/streams/data/draft"))
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body(
            ok(
                {
                    "download": {"url": match.regex(DRAFT_URL, regex=HTTPS_URL)},
                    "security_context": {"value": match.regex(DRAFT_CONTEXT, regex=B64URL)},
                    "draft_rev": match.int(1),
                }
            ),
            content_type="application/json",
        )
    )
    storage = _Storage({DRAFT_URL: draft_body})

    with pact.serve() as server:
        patient = _patients(str(server.url), storage).get(PATIENT_ID)

    assert patient.record == MARIA_DRAFT
    assert patient.from_draft is True
    assert patient.draft_rev == 1


def test_update_patient_reserves_the_next_version_under_the_conflict_guard(pact: Pact) -> None:
    """🇺🇸 Read the index → reserve with `expected_latest_version_id` and a new summary → `PUT` → commit.

    🇧🇷 Ler o índice → reservar com `expected_latest_version_id` e resumo novo → `PUT` → commit.
    """
    renamed = MARIA.model_copy(update={"display_name": "Maria S."})
    size = _sealed_length(renamed)
    state = "a patient has one committed version"
    declare_clock(pact)
    _declare_open_patient(
        pact,
        state=state,
        description="an SDK process opens the latest version of a patient",
        stream=_stream(size=_sealed_length(MARIA)),
    )
    name, params = workspace_state(state, document_id=PATIENT_ID, security_group_id=SECURITY_GROUP_ID)
    (
        pact.upon_receiving("an SDK process reserves the next version of a patient's data stream")
        .given(name, params)
        .with_request("POST", _patient_path("/streams/data/versions"))
        .with_headers(signed_headers())
        .with_body(
            {
                "content_length": match.int(size),
                "encrypted_index": encrypted(_summary_payload("patients", PatientSummary.of(renamed, ["diabetes"]))),
                "expected_latest_version_id": match.str(VERSION_1),
            },
            content_type="application/json",
        )
        .will_respond_with(201)
        .with_body(ok({"staged": literal(True), **_reservation(VERSION_2, size)}), content_type="application/json")
    )
    _declare_commit(
        pact,
        resource="patients",
        document_id=PATIENT_ID,
        version_id=VERSION_2,
        description="an SDK process commits the next version of a patient",
        stream=_stream(size=size),
    )
    storage = _Storage()

    with pact.serve() as server:
        patient = _patients(str(server.url), storage).update(PATIENT_ID, renamed, expected_latest_version_id=VERSION_1)

    assert len(storage.puts) == 1
    assert len(storage.puts[0].content) == size
    assert patient.version_id == VERSION_2
    assert patient.tags == ["diabetes"]


def test_archive_patient_is_a_patch_only_reservation(pact: Pact) -> None:
    """🇺🇸 Only the flag travels: no `content_length`, no upload, no commit.

    🇧🇷 Só a flag viaja: sem `content_length`, sem upload, sem commit.
    """
    name, params = workspace_state(
        "a patient has one committed version", document_id=PATIENT_ID, security_group_id=SECURITY_GROUP_ID
    )
    declare_clock(pact)
    (
        pact.upon_receiving("an SDK process archives a patient without a new version")
        .given(name, params)
        .with_request("POST", _patient_path("/streams/data/versions"))
        .with_headers(signed_headers())
        .with_body({"is_archived": literal(True)}, content_type="application/json")
        .will_respond_with(200)
        .with_body(
            ok(
                {
                    "document": _index(
                        PATIENT_ID,
                        resource="patients",
                        summary=MARIA_SUMMARY,
                        stream=_stream(size=_sealed_length(MARIA)),
                        is_archived=True,
                    )
                }
            ),
            content_type="application/json",
        )
    )
    storage = _Storage()

    with pact.serve() as server:
        index = _patients(str(server.url), storage).archive(PATIENT_ID)

    assert index.is_archived is True
    assert storage.puts == []


def test_list_patients_opens_each_summary_without_downloading(pact: Pact) -> None:
    """🇺🇸 One page; each row's `encrypted_index` opens under its DEK; `next_cursor: null` ends the walk.

    🇧🇷 Uma página; o `encrypted_index` de cada linha abre sob a DEK; `next_cursor: null` encerra a caminhada.
    """
    name, params = workspace_state(
        "a patient has one committed version", document_id=PATIENT_ID, security_group_id=SECURITY_GROUP_ID
    )
    declare_clock(pact)
    (
        pact.upon_receiving("an SDK process lists the patients of a workspace")
        .given(name, params)
        .with_request("GET", path(_PATIENTS[0], pattern=_PATIENTS[1], expression=_PATIENTS[2]))
        .with_query_parameter("limit", "50")
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body(
            ok(
                {
                    "items": match.each_like(
                        _index(
                            PATIENT_ID,
                            resource="patients",
                            summary=MARIA_SUMMARY,
                            stream=_stream(size=_sealed_length(MARIA)),
                        )
                    ),
                    "next_cursor": None,
                }
            ),
            content_type="application/json",
        )
    )
    storage = _Storage()

    with pact.serve() as server:
        rows = list(_patients(str(server.url), storage).iter_all())

    assert [row.id for row in rows] == [PATIENT_ID]
    assert rows[0].summary == MARIA_SUMMARY


def test_reserving_while_another_version_is_pending_backs_off_then_raises(pact: Pact) -> None:
    """🇺🇸 `409 DocumentVersionPending` is retried briefly, like the web app, then surfaced as `ConflictError`.

    🇧🇷 `409 DocumentVersionPending` é retentado por pouco tempo, como no app web, depois vira `ConflictError`.
    """
    state = "a patient has a committed version and another one pending"
    declare_clock(pact)
    _declare_open_patient(
        pact,
        state=state,
        description="an SDK process opens a patient that has a version pending",
        stream=_stream(size=_sealed_length(MARIA), pending=VERSION_2),
    )
    name, params = workspace_state(state, document_id=PATIENT_ID, security_group_id=SECURITY_GROUP_ID)
    (
        pact.upon_receiving("an SDK process tries to reserve a version while another is pending")
        .given(name, params)
        .with_request("POST", _patient_path("/streams/data/versions"))
        .with_headers(signed_headers())
        .with_body(
            {
                "content_length": match.int(_sealed_length(MARIA)),
                "encrypted_index": encrypted(_summary_payload("patients", MARIA_SUMMARY)),
            },
            content_type="application/json",
        )
        .will_respond_with(409)
        .with_body(failure("DocumentVersionPending"), content_type="application/json")
    )

    with pact.serve() as server, pytest.raises(ConflictError) as raised:
        _patients(str(server.url), _Storage()).update(PATIENT_ID, MARIA)

    assert raised.value.code == "DocumentVersionPending"


# -- exams ---------------------------------------------------------------------


def test_create_exam_has_no_stream_segment_and_links_the_patient_in_clear_meta(pact: Pact) -> None:
    """🇺🇸 Exams have one stream: no `/streams/...` in the version routes; only `patient_id` goes in clear.

    🇧🇷 Exames têm um fluxo: sem `/streams/...` nas rotas de versão; só `patient_id` vai em claro.
    """
    size = _sealed_length(SCAN)
    wrapped = seal_content(GROUP_KEY, DEK, DOCUMENT_DEK_INFO, label="document/wrapped-dek")
    declare_clock(pact)
    name, params = workspace_state(
        "the SDK session holds the key of a security group", security_group_id=SECURITY_GROUP_ID
    )
    (
        pact.upon_receiving("an SDK process creates an exam and reserves its first version")
        .given(name, params)
        .with_request("POST", path(_EXAMS[0], pattern=_EXAMS[1], expression=_EXAMS[2]))
        .with_headers(signed_headers())
        .with_body(
            {
                "security_group_id": literal(SECURITY_GROUP_ID),
                "encrypted_keys": {SECURITY_GROUP_ID: encrypted(wrapped)},
                "content_length": match.int(size),
                "encrypted_index": encrypted(_summary_payload("exams", SCAN_SUMMARY)),
                "stream": literal("data"),
                "meta": {"patient_id": match.str(PATIENT_ID)},
            },
            content_type="application/json",
        )
        .will_respond_with(201)
        .with_body(
            ok({"document": {"document_id": match.str(EXAM_ID)}, **_reservation(VERSION_1, size)}),
            content_type="application/json",
        )
    )
    _declare_commit(
        pact,
        resource="exams",
        document_id=EXAM_ID,
        version_id=VERSION_1,
        description="an SDK process commits the first version of an exam",
        stream=_stream(size=size),
    )
    storage = _Storage()

    with pact.serve() as server:
        exam = _exams(str(server.url), storage).create(SCAN, patient_id=PATIENT_ID, security_group=SECURITY_GROUP_ID)

    assert exam.id == EXAM_ID
    assert exam.patient_id == PATIENT_ID
    assert len(storage.puts[0].content) == size


def test_open_exam_decrypts_the_report(pact: Pact) -> None:
    """🇺🇸 `GET .../exams/{id}` without a stream query; the report opens under the version's key.

    🇧🇷 `GET .../exams/{id}` sem query de fluxo; o laudo abre sob a chave da versão.
    """
    name, params = workspace_state(
        "an exam has one committed version", document_id=EXAM_ID, security_group_id=SECURITY_GROUP_ID
    )
    declare_clock(pact)
    (
        pact.upon_receiving("an SDK process opens the latest version of an exam")
        .given(name, params)
        .with_request(
            "GET",
            path(
                f"{_BASE}/exams/{EXAM_ID}",
                pattern=rf"{_WS}/exams/[^/]+$",
                expression=f"{_WS_EXPR}/exams/${{document_id}}",
            ),
        )
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body(
            ok(
                {
                    "document": _index(
                        EXAM_ID,
                        resource="exams",
                        summary=SCAN_SUMMARY,
                        stream=_stream(size=_sealed_length(SCAN)),
                        meta={"patient_id": match.str(PATIENT_ID)},
                    ),
                    "version": {"version_id": match.str(VERSION_1)},
                    "security_context": {"value": match.regex(CONTEXT, regex=B64URL)},
                    "download": {"url": match.regex(DOWNLOAD_URL, regex=HTTPS_URL)},
                }
            ),
            content_type="application/json",
        )
    )
    storage = _Storage({DOWNLOAD_URL: _sealed_version(SCAN, label="exam/v1")})

    with pact.serve() as server:
        exam = _exams(str(server.url), storage).get(EXAM_ID)

    assert exam.record == SCAN
    assert exam.summary == SCAN_SUMMARY
    assert exam.patient_id == PATIENT_ID
