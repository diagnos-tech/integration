"""🇺🇸 Shared ground for the document contract tests: fixed records, vault-shaped bodies, and the SDK wired to Pact.

`test_patients.py` and `test_exams.py` declare the interactions; this
module holds what both need — the fixed keys and records, the index,
stream and reservation bodies the vault answers with, an in-memory object
store, and `Patients`/`Exams` built on a real transport pointed at the Pact
mock. The object bodies are sealed by `_crypto.py`, an implementation
independent of the SDK, following the web app's composition.

🇧🇷 Base comum dos testes de contrato de documentos: registros fixos, corpos no formato do cofre, e o SDK ligado ao Pact.

`test_patients.py` e `test_exams.py` declaram as interações; este módulo
guarda o que os dois precisam — as chaves e registros fixos, os corpos de
índice, stream e reserva com que o cofre responde, um armazenamento de
objetos em memória, e `Patients`/`Exams` montados sobre um transporte de
verdade apontado para o mock do Pact. Os corpos de objeto são selados pelo
`_crypto.py`, uma implementação independente do SDK, seguindo a composição
do app web.
"""

from __future__ import annotations

from typing import Any

import httpx
from diagnos import ExamRecord, ExamSummary, PatientRecord, PatientSummary
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
    encrypted,
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
UPLOAD_URL = "https://storage.diagnosusercontent.com/upload?X-Amz-Signature=contract"
DOWNLOAD_URL = "https://storage.diagnosusercontent.com/download?X-Amz-Signature=contract"
DRAFT_URL = "https://storage.diagnosusercontent.com/draft?X-Amz-Signature=contract"

MARIA = PatientRecord(legal_name="Maria da Silva", display_name="Maria", birth_date="1984-03-02")
MARIA_DRAFT = MARIA.model_copy(update={"display_name": "Maria (rascunho)"})
MARIA_SUMMARY = PatientSummary.of(MARIA, ["diabetes"])
SCAN = ExamRecord(title="RM de crânio", modality="MR", exam_date="2026-09-01")
SCAN_SUMMARY = ExamSummary.of(SCAN)

WS_PATTERN = rf"^{EXTERNAL_PREFIX}/workspaces/[^/]+"
WS_EXPR = f"{EXTERNAL_PREFIX}/workspaces/${{workspace_id}}"
BASE = f"{EXTERNAL_PREFIX}/workspaces/{WORKSPACE_ID}"


def sealed_length(record: BaseModel) -> int:
    """🇺🇸 `content_length` the SDK declares: the JSON record plus 44 bytes of framing and tag.

    🇧🇷 O `content_length` que o SDK declara: o registro JSON mais 44 bytes de enquadramento e tag.
    """
    return len(record.model_dump_json(exclude_none=True).encode("utf-8")) + 44


def summary_payload(resource: str, summary: BaseModel) -> dict[str, str]:
    """🇺🇸 A real `encrypted_index` under the fixed document DEK. 🇧🇷 Um `encrypted_index` real sob a DEK fixa."""
    plaintext = summary.model_dump_json(exclude_none=True).encode("utf-8")
    return seal_content(DEK, plaintext, INDEX_INFO[resource], label=f"{resource}/index")


def index_body(
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
        "encrypted_index": encrypted(summary_payload(resource, summary)),
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


def stream_body(*, size: int, pending: str | None = None, draft: dict[str, object] | None = None) -> dict[str, object]:
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


def reservation_body(version_id: str, size: int) -> dict[str, object]:
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


def keyring() -> Keyring:
    """🇺🇸 The session plus the one group key the approval in `test_session.py` hands out.

    🇧🇷 A sessão mais a chave de grupo que a aprovação de `test_session.py` entrega.
    """
    return Keyring(
        enrollment_id="enr-contract",
        session=session_keys(),
        group_keys={SECURITY_GROUP_ID: SecretBox.from_bytes(bytearray(GROUP_KEY))},
    )


class Storage:
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


def engine(
    url: str, resource: ResourceKind, record: type[Any], summary: type[Any], storage: Storage
) -> VersionedDocuments[Any, Any]:
    """🇺🇸 The SDK's real engine over the mock server, with the contract keyring. 🇧🇷 O motor real do SDK sobre o mock."""
    return VersionedDocuments(
        make_transport(url, storage=storage),
        keyring,
        EntropyMixer(),
        workspace_id=WORKSPACE_ID,
        resource=resource,
        record_model=record,
        summary_model=summary,
        sleep=lambda seconds: None,
    )


def patients_for(url: str, storage: Storage) -> Patients:
    """🇺🇸 `vault.patients` over the mock server. 🇧🇷 `vault.patients` sobre o mock."""
    return Patients(engine(url, "patients", PatientRecord, PatientSummary, storage))


def exams_for(url: str, storage: Storage) -> Exams:
    """🇺🇸 `vault.exams` over the mock server. 🇧🇷 `vault.exams` sobre o mock."""
    return Exams(engine(url, "exams", ExamRecord, ExamSummary, storage))


def sealed_version(record: BaseModel, *, label: str) -> bytes:
    """🇺🇸 `VERSION_1`'s object body, sealed by the oracle. 🇧🇷 O corpo do objeto de `VERSION_1`, selado pelo oráculo."""
    key = content_key(DEK, VERSION_1, CONTEXT)
    return seal_body(key, record.model_dump_json(exclude_none=True).encode("utf-8"), VERSION_CONTENT_INFO, label=label)


# -- interactions --------------------------------------------------------------

PATIENTS_ROUTE = (f"{BASE}/patients", rf"{WS_PATTERN}/patients$", f"{WS_EXPR}/patients")
EXAMS_ROUTE = (f"{BASE}/exams", rf"{WS_PATTERN}/exams$", f"{WS_EXPR}/exams")


def patient_path(suffix: str = "") -> Any:
    """🇺🇸 `.../patients/{document_id}{suffix}`, rebuilt from provider state at verification.

    🇧🇷 `.../patients/{document_id}{suffix}`, remontado a partir do provider state na verificação.
    """
    return path(
        f"{BASE}/patients/{PATIENT_ID}{suffix}",
        pattern=rf"{WS_PATTERN}/patients/[^/]+{suffix}$",
        expression=f"{WS_EXPR}/patients/${{document_id}}{suffix}",
    )


def declare_open_patient(pact: Pact, *, state: str, description: str, stream: dict[str, object]) -> None:
    """🇺🇸 `GET .../patients/{id}?stream=data` under `state`, answering the index plus the latest version.

    🇧🇷 `GET .../patients/{id}?stream=data` sob `state`, respondendo o índice mais a versão corrente.
    """
    name, params = workspace_state(
        state, document_id=PATIENT_ID, version_id=VERSION_1, security_group_id=SECURITY_GROUP_ID
    )
    (
        pact.upon_receiving(description)
        .given(name, params)
        .with_request("GET", patient_path())
        .with_query_parameter("stream", "data")
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body(
            ok(
                {
                    "document": index_body(PATIENT_ID, resource="patients", summary=MARIA_SUMMARY, stream=stream),
                    "version": {"version_id": match.str(VERSION_1)},
                    "security_context": {"value": match.regex(CONTEXT, regex=B64URL)},
                    "download": {"url": match.regex(DOWNLOAD_URL, regex=HTTPS_URL)},
                }
            ),
            content_type="application/json",
        )
    )


def declare_commit(
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
        f"{BASE}/{resource}/{document_id}{segment}/versions/{version_id}/commit",
        pattern=rf"{WS_PATTERN}/{resource}/[^/]+{segment}/versions/[^/]+/commit$",
        expression=f"{WS_EXPR}/{resource}/${{document_id}}{segment}/versions/${{version_id}}/commit",
    )
    (
        pact.upon_receiving(description)
        .given(name, params)
        .with_request("POST", request_path)
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body(
            ok({"document": index_body(document_id, resource=resource, summary=summary, stream=stream, meta=meta)}),
            content_type="application/json",
        )
    )


# -- patients ------------------------------------------------------------------
