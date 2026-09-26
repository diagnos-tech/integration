"""🇺🇸 Versioned patients (`docs/PROTOCOL.md §8`): what the SDK asks of `/patients`, and reads back.

Each test drives the SDK's real `Patients` against the Pact mock:
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

🇧🇷 Pacientes versionados (`docs/PROTOCOL.md §8`): o que o SDK pede a `/patients`, e o que lê de volta.

Cada teste conduz os `Patients` de verdade do SDK contra o mock do
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

import pytest
from diagnos import ConflictError, PatientSummary
from pact import Pact, match

from _crypto import (
    DOCUMENT_DEK_INFO,
    DRAFT_CONTENT_INFO,
    content_key,
    seal_body,
    seal_content,
)
from _documents import (
    DEK,
    DOWNLOAD_URL,
    DRAFT_AT,
    DRAFT_CONTEXT,
    DRAFT_URL,
    GROUP_KEY,
    MARIA,
    MARIA_DRAFT,
    MARIA_SUMMARY,
    PATIENT_ID,
    PATIENTS_ROUTE,
    UPLOAD_URL,
    VERSION_1,
    VERSION_2,
    Storage,
    declare_commit,
    declare_open_patient,
    index_body,
    patient_path,
    patients_for,
    reservation_body,
    sealed_length,
    sealed_version,
    stream_body,
    summary_payload,
)
from _wire import (
    ACCOUNT_ID,
    B64URL,
    HTTPS_URL,
    SECURITY_GROUP_ID,
    declare_clock,
    encrypted,
    failure,
    from_state,
    instant,
    literal,
    ok,
    path,
    signed_headers,
    workspace_state,
)


def test_create_patient_reserves_uploads_and_commits_the_first_version(pact: Pact) -> None:
    """🇺🇸 One group, the DEK sealed for it, the sealed size, the sealed summary → `PUT` → commit.

    🇧🇷 Um grupo, a DEK selada para ele, o tamanho selado, o resumo selado → `PUT` → commit.
    """
    size = sealed_length(MARIA)
    wrapped = seal_content(GROUP_KEY, DEK, DOCUMENT_DEK_INFO, label="document/wrapped-dek")
    declare_clock(pact)
    name, params = workspace_state(
        "the SDK session holds the key of a security group", security_group_id=SECURITY_GROUP_ID
    )
    (
        pact.upon_receiving("an SDK process creates a patient and reserves its first version")
        .given(name, params)
        .with_request("POST", path(PATIENTS_ROUTE[0], pattern=PATIENTS_ROUTE[1], expression=PATIENTS_ROUTE[2]))
        .with_headers(signed_headers())
        .with_body(
            {
                "security_group_id": literal(SECURITY_GROUP_ID),
                "encrypted_keys": {SECURITY_GROUP_ID: encrypted(wrapped)},
                "content_length": match.int(size),
                "encrypted_index": encrypted(summary_payload("patients", MARIA_SUMMARY)),
                "stream": literal("data"),
            },
            content_type="application/json",
        )
        .will_respond_with(201)
        .with_body(
            ok({"document": {"document_id": match.str(PATIENT_ID)}, **reservation_body(VERSION_1, size)}),
            content_type="application/json",
        )
    )
    declare_commit(
        pact,
        resource="patients",
        document_id=PATIENT_ID,
        version_id=VERSION_1,
        description="an SDK process commits the first version of a patient",
        stream=stream_body(size=size),
    )
    storage = Storage()

    with pact.serve() as server:
        patient = patients_for(str(server.url), storage).create(
            MARIA, security_group=SECURITY_GROUP_ID, tags=["diabetes"]
        )

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
    declare_open_patient(
        pact,
        state="a patient has one committed version",
        description="an SDK process opens the latest version of a patient",
        stream=stream_body(size=sealed_length(MARIA)),
    )
    storage = Storage({DOWNLOAD_URL: sealed_version(MARIA, label="patient/v1")})

    with pact.serve() as server:
        patient = patients_for(str(server.url), storage).get(PATIENT_ID)

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
    declare_open_patient(
        pact,
        state=state,
        description="an SDK process opens a patient whose draft is newer than its latest version",
        stream=stream_body(
            size=sealed_length(MARIA),
            draft={
                "rev": match.int(1),
                "size": match.int(len(draft_body)),
                "updated_at": instant(DRAFT_AT),
                "updated_by": match.str(ACCOUNT_ID),
            },
        ),
    )
    name, params = workspace_state(
        state, document_id=PATIENT_ID, version_id=VERSION_1, security_group_id=SECURITY_GROUP_ID
    )
    (
        pact.upon_receiving("an SDK process resolves the draft head of a patient's data stream")
        .given(name, params)
        .with_request("GET", patient_path("/streams/data/draft"))
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
    storage = Storage({DRAFT_URL: draft_body})

    with pact.serve() as server:
        patient = patients_for(str(server.url), storage).get(PATIENT_ID)

    assert patient.record == MARIA_DRAFT
    assert patient.from_draft is True
    assert patient.draft_rev == 1


def test_update_patient_reserves_the_next_version_under_the_conflict_guard(pact: Pact) -> None:
    """🇺🇸 Read the index → reserve with `expected_latest_version_id` and a new summary → `PUT` → commit.

    🇧🇷 Ler o índice → reservar com `expected_latest_version_id` e resumo novo → `PUT` → commit.
    """
    renamed = MARIA.model_copy(update={"display_name": "Maria S."})
    size = sealed_length(renamed)
    state = "a patient has one committed version"
    declare_clock(pact)
    declare_open_patient(
        pact,
        state=state,
        description="an SDK process opens the latest version of a patient",
        stream=stream_body(size=sealed_length(MARIA)),
    )
    name, params = workspace_state(
        state, document_id=PATIENT_ID, version_id=VERSION_1, security_group_id=SECURITY_GROUP_ID
    )
    (
        pact.upon_receiving("an SDK process reserves the next version of a patient's data stream")
        .given(name, params)
        .with_request("POST", patient_path("/streams/data/versions"))
        .with_headers(signed_headers())
        .with_body(
            {
                "content_length": match.int(size),
                "encrypted_index": encrypted(summary_payload("patients", PatientSummary.of(renamed, ["diabetes"]))),
                "expected_latest_version_id": from_state(VERSION_1, "version_id"),
            },
            content_type="application/json",
        )
        .will_respond_with(201)
        .with_body(ok({"staged": literal(True), **reservation_body(VERSION_2, size)}), content_type="application/json")
    )
    declare_commit(
        pact,
        resource="patients",
        document_id=PATIENT_ID,
        version_id=VERSION_2,
        description="an SDK process commits the next version of a patient",
        stream=stream_body(size=size),
    )
    storage = Storage()

    with pact.serve() as server:
        patient = patients_for(str(server.url), storage).update(
            PATIENT_ID, renamed, expected_latest_version_id=VERSION_1
        )

    assert len(storage.puts) == 1
    assert len(storage.puts[0].content) == size
    assert patient.version_id == VERSION_2
    assert patient.tags == ["diabetes"]


def test_archive_patient_is_a_patch_only_reservation(pact: Pact) -> None:
    """🇺🇸 Only the flag travels: no `content_length`, no upload, no commit.

    🇧🇷 Só a flag viaja: sem `content_length`, sem upload, sem commit.
    """
    name, params = workspace_state(
        "a patient has one committed version",
        document_id=PATIENT_ID,
        version_id=VERSION_1,
        security_group_id=SECURITY_GROUP_ID,
    )
    declare_clock(pact)
    (
        pact.upon_receiving("an SDK process archives a patient without a new version")
        .given(name, params)
        .with_request("POST", patient_path("/streams/data/versions"))
        .with_headers(signed_headers())
        .with_body({"is_archived": literal(True)}, content_type="application/json")
        .will_respond_with(200)
        .with_body(
            ok(
                {
                    "document": index_body(
                        PATIENT_ID,
                        resource="patients",
                        summary=MARIA_SUMMARY,
                        stream=stream_body(size=sealed_length(MARIA)),
                        is_archived=True,
                    )
                }
            ),
            content_type="application/json",
        )
    )
    storage = Storage()

    with pact.serve() as server:
        index = patients_for(str(server.url), storage).archive(PATIENT_ID)

    assert index.is_archived is True
    assert storage.puts == []


def test_list_patients_opens_each_summary_without_downloading(pact: Pact) -> None:
    """🇺🇸 One page; each row's `encrypted_index` opens under its DEK; `next_cursor: null` ends the walk.

    🇧🇷 Uma página; o `encrypted_index` de cada linha abre sob a DEK; `next_cursor: null` encerra a caminhada.
    """
    name, params = workspace_state(
        "a patient has one committed version",
        document_id=PATIENT_ID,
        version_id=VERSION_1,
        security_group_id=SECURITY_GROUP_ID,
    )
    declare_clock(pact)
    (
        pact.upon_receiving("an SDK process lists the patients of a workspace")
        .given(name, params)
        .with_request("GET", path(PATIENTS_ROUTE[0], pattern=PATIENTS_ROUTE[1], expression=PATIENTS_ROUTE[2]))
        .with_query_parameter("limit", "50")
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body(
            ok(
                {
                    "items": match.each_like(
                        index_body(
                            PATIENT_ID,
                            resource="patients",
                            summary=MARIA_SUMMARY,
                            stream=stream_body(size=sealed_length(MARIA)),
                        )
                    ),
                    "next_cursor": None,
                }
            ),
            content_type="application/json",
        )
    )
    storage = Storage()

    with pact.serve() as server:
        rows = list(patients_for(str(server.url), storage).iter_all())

    assert [row.id for row in rows] == [PATIENT_ID]
    assert rows[0].summary == MARIA_SUMMARY


def test_reserving_while_another_version_is_pending_backs_off_then_raises(pact: Pact) -> None:
    """🇺🇸 `409 DocumentVersionPending` is retried briefly, like the web app, then surfaced as `ConflictError`.

    🇧🇷 `409 DocumentVersionPending` é retentado por pouco tempo, como no app web, depois vira `ConflictError`.
    """
    state = "a patient has a committed version and another one pending"
    declare_clock(pact)
    declare_open_patient(
        pact,
        state=state,
        description="an SDK process opens a patient that has a version pending",
        stream=stream_body(size=sealed_length(MARIA), pending=VERSION_2),
    )
    name, params = workspace_state(
        state, document_id=PATIENT_ID, version_id=VERSION_1, security_group_id=SECURITY_GROUP_ID
    )
    (
        pact.upon_receiving("an SDK process tries to reserve a version while another is pending")
        .given(name, params)
        .with_request("POST", patient_path("/streams/data/versions"))
        .with_headers(signed_headers())
        .with_body(
            {
                "content_length": match.int(sealed_length(MARIA)),
                "encrypted_index": encrypted(summary_payload("patients", MARIA_SUMMARY)),
            },
            content_type="application/json",
        )
        .will_respond_with(409)
        .with_body(failure("DocumentVersionPending"), content_type="application/json")
    )

    with pact.serve() as server, pytest.raises(ConflictError) as raised:
        patients_for(str(server.url), Storage()).update(PATIENT_ID, MARIA)

    assert raised.value.code == "DocumentVersionPending"


# -- exams ---------------------------------------------------------------------
