"""🇺🇸 Versioned exams (`docs/PROTOCOL.md §8`): no stream segment, the patient linked in clear `meta`, the report opened.

Same composition as `test_patients.py` (shared ground in `_documents.py`); an exam differs in its routes and in
what it may send in clear.

🇧🇷 Exames versionados (`docs/PROTOCOL.md §8`): sem segmento de stream, o paciente em `meta` claro, o laudo aberto.

A mesma composição de `test_patients.py` (base comum em `_documents.py`); um exame muda nas rotas e no que
pode mandar em claro.
"""

from __future__ import annotations

from pact import Pact, match

from _crypto import (
    DOCUMENT_DEK_INFO,
    seal_content,
)
from _documents import (
    BASE,
    CONTEXT,
    DEK,
    DOWNLOAD_URL,
    EXAM_ID,
    EXAMS_ROUTE,
    GROUP_KEY,
    PATIENT_ID,
    SCAN,
    SCAN_SUMMARY,
    VERSION_1,
    WS_EXPR,
    WS_PATTERN,
    Storage,
    declare_commit,
    exams_for,
    index_body,
    reservation_body,
    sealed_length,
    sealed_version,
    stream_body,
    summary_payload,
)
from _wire import (
    B64URL,
    HTTPS_URL,
    SECURITY_GROUP_ID,
    declare_clock,
    encrypted,
    literal,
    ok,
    path,
    signed_headers,
    workspace_state,
)


def test_create_exam_has_no_stream_segment_and_links_the_patient_in_clear_meta(pact: Pact) -> None:
    """🇺🇸 Exams have one stream: no `/streams/...` in the version routes; only `patient_id` goes in clear.

    🇧🇷 Exames têm um fluxo: sem `/streams/...` nas rotas de versão; só `patient_id` vai em claro.
    """
    size = sealed_length(SCAN)
    wrapped = seal_content(GROUP_KEY, DEK, DOCUMENT_DEK_INFO, label="document/wrapped-dek")
    declare_clock(pact)
    name, params = workspace_state(
        "the SDK session holds the key of a security group", security_group_id=SECURITY_GROUP_ID
    )
    (
        pact.upon_receiving("an SDK process creates an exam and reserves its first version")
        .given(name, params)
        .with_request("POST", path(EXAMS_ROUTE[0], pattern=EXAMS_ROUTE[1], expression=EXAMS_ROUTE[2]))
        .with_headers(signed_headers())
        .with_body(
            {
                "security_group_id": literal(SECURITY_GROUP_ID),
                "encrypted_keys": {SECURITY_GROUP_ID: encrypted(wrapped)},
                "content_length": match.int(size),
                "encrypted_index": encrypted(summary_payload("exams", SCAN_SUMMARY)),
                "stream": literal("data"),
                "meta": {"patient_id": match.str(PATIENT_ID)},
            },
            content_type="application/json",
        )
        .will_respond_with(201)
        .with_body(
            ok({"document": {"document_id": match.str(EXAM_ID)}, **reservation_body(VERSION_1, size)}),
            content_type="application/json",
        )
    )
    declare_commit(
        pact,
        resource="exams",
        document_id=EXAM_ID,
        version_id=VERSION_1,
        description="an SDK process commits the first version of an exam",
        stream=stream_body(size=size),
    )
    storage = Storage()

    with pact.serve() as server:
        exam = exams_for(str(server.url), storage).create(SCAN, patient_id=PATIENT_ID, security_group=SECURITY_GROUP_ID)

    assert exam.id == EXAM_ID
    assert exam.patient_id == PATIENT_ID
    assert len(storage.puts[0].content) == size


def test_open_exam_decrypts_the_report(pact: Pact) -> None:
    """🇺🇸 `GET .../exams/{id}` without a stream query; the report opens under the version's key.

    🇧🇷 `GET .../exams/{id}` sem query de fluxo; o laudo abre sob a chave da versão.
    """
    name, params = workspace_state(
        "an exam has one committed version",
        document_id=EXAM_ID,
        version_id=VERSION_1,
        security_group_id=SECURITY_GROUP_ID,
    )
    declare_clock(pact)
    (
        pact.upon_receiving("an SDK process opens the latest version of an exam")
        .given(name, params)
        .with_request(
            "GET",
            path(
                f"{BASE}/exams/{EXAM_ID}",
                pattern=rf"{WS_PATTERN}/exams/[^/]+$",
                expression=f"{WS_EXPR}/exams/${{document_id}}",
            ),
        )
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body(
            ok(
                {
                    "document": index_body(
                        EXAM_ID,
                        resource="exams",
                        summary=SCAN_SUMMARY,
                        stream=stream_body(size=sealed_length(SCAN)),
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
    storage = Storage({DOWNLOAD_URL: sealed_version(SCAN, label="exam/v1")})

    with pact.serve() as server:
        exam = exams_for(str(server.url), storage).get(EXAM_ID)

    assert exam.record == SCAN
    assert exam.summary == SCAN_SUMMARY
    assert exam.patient_id == PATIENT_ID
