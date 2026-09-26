"""🇺🇸 Request/response shapes that exist only at the HTTP boundary — never reused by the SDK.

`diagnos`'s own models (`PatientRecord`, `ExamRecord`, `DocumentIndex`,
`DriveNode`, `Page`) are returned to callers exactly as the SDK produces
them (`CONVENTIONS.md`: reuse, never reimplement); the types below are the
thin envelopes an HTTP body needs around them — a create call bundles a
record with the `security_group` it belongs to, a listing of drive nodes
needs each node's name decrypted alongside it. None of this belongs in the
SDK, because none of it means anything outside of "a JSON body arrived over
HTTP".

🇧🇷 Formas de requisição/resposta que existem só na fronteira HTTP — nunca
reaproveitadas pelo SDK.

Os próprios modelos do `diagnos` (`PatientRecord`, `ExamRecord`,
`DocumentIndex`, `DriveNode`, `Page`) são devolvidos a quem chama exatamente
como o SDK os produz (`CONVENTIONS.md`: reusar, nunca reimplementar); os
tipos abaixo são os envelopes finos que um corpo HTTP precisa ao redor
deles — uma chamada de criação empacota um registro com o `security_group`
a que pertence, uma listagem de nós de drive precisa do nome decifrado de
cada nó junto. Nada disto pertence ao SDK, porque nada disto significa algo
fora de "um corpo JSON chegou por HTTP".
"""

from __future__ import annotations

from diagnos import DriveNode, ExamRecord, PatientRecord
from pydantic import BaseModel, ConfigDict, Field

_EXPECT = (
    "🇺🇸 The `latest_version_id` you read; the write is refused with 409 if another version was saved since. "
    "🇧🇷 O `latest_version_id` que você leu; a gravação é recusada com 409 se outra versão foi salva depois."
)


class PatientCreateRequest(BaseModel):
    """🇺🇸 Body of `POST /v1/patients`. 🇧🇷 Corpo de `POST /v1/patients`."""

    model_config = ConfigDict(extra="forbid")

    record: PatientRecord
    security_group: str = Field(min_length=1, description="🇺🇸 The one group the patient belongs to. 🇧🇷 O grupo.")
    tags: list[str] = Field(default_factory=list, description="🇺🇸 Sealed list labels. 🇧🇷 Rótulos selados.")
    specialist_ids: list[str] | None = None


class PatientUpdateRequest(BaseModel):
    """🇺🇸 Body of `PUT /v1/patients/{id}`: a complete new record.

    🇧🇷 Corpo de `PUT /v1/patients/{id}`: o registro completo.
    """

    model_config = ConfigDict(extra="forbid")

    record: PatientRecord
    tags: list[str] | None = Field(default=None, description="🇺🇸 `null` keeps the tags. 🇧🇷 `null` mantém as tags.")
    specialist_ids: list[str] | None = None
    expected_latest_version_id: str | None = Field(default=None, description=_EXPECT)


class ExamCreateRequest(BaseModel):
    """🇺🇸 Body of `POST /v1/exams`. 🇧🇷 Corpo de `POST /v1/exams`."""

    model_config = ConfigDict(extra="forbid")

    record: ExamRecord
    patient_id: str = Field(min_length=1)
    security_group: str = Field(min_length=1)


class ExamUpdateRequest(BaseModel):
    """🇺🇸 Body of `PUT /v1/exams/{id}`: a complete new record. 🇧🇷 Corpo de `PUT /v1/exams/{id}`: o registro completo."""

    model_config = ConfigDict(extra="forbid")

    record: ExamRecord
    expected_latest_version_id: str | None = Field(default=None, description=_EXPECT)


class NodeView(BaseModel):
    """🇺🇸 One drive node plus its decrypted name — `DriveNode` alone keeps the name sealed.

    🇧🇷 Um nó de drive mais seu nome decifrado — `DriveNode` sozinho mantém o nome selado.
    """

    model_config = ConfigDict(frozen=True)

    node: DriveNode
    name: str | None = None


class FolderCreateRequest(BaseModel):
    """🇺🇸 Body of `POST /v1/drives/{sg}/folders`. 🇧🇷 Corpo de `POST /v1/drives/{sg}/folders`."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="🇺🇸 Sealed before it leaves. 🇧🇷 Selado antes de sair.")
    parent_id: str | None = Field(default=None, description="🇺🇸 Parent folder node id. 🇧🇷 Id da pasta-mãe.")


class FolderCreated(BaseModel):
    """🇺🇸 A new folder's node id — folders have no content, so there is nothing else to report.

    🇧🇷 O id do nó da pasta nova — pastas não têm conteúdo, então não há mais nada a reportar.
    """

    model_config = ConfigDict(frozen=True)

    node_id: str


class ClientIdentityView(BaseModel):
    """🇺🇸 The mTLS identity of the caller, as `GET /v1/session` reports it.

    🇧🇷 A identidade mTLS de quem chama, como `GET /v1/session` reporta.
    """

    model_config = ConfigDict(frozen=True)

    common_name: str
    serial: str


class ErrorDetail(BaseModel):
    """🇺🇸 The body of every non-2xx response: what went wrong, for a program and for a person.

    🇧🇷 O corpo de toda resposta não-2xx: o que deu errado, para um programa e para uma pessoa.
    """

    model_config = ConfigDict(frozen=True)

    code: str = Field(
        description="🇺🇸 Stable and machine-readable: branch on it, never on `message`. "
        "🇧🇷 Estável e legível por máquina: decida por ele, nunca pela `message`."
    )
    message: str = Field(description="🇺🇸 For a person; its wording may change. 🇧🇷 Para uma pessoa; o texto pode mudar.")
    trace_id: str | None = Field(
        default=None,
        description="🇺🇸 The vault's trace id when the failure came from the vault — what a support ticket needs. "
        "🇧🇷 O trace id do cofre quando a falha veio do cofre — o que um chamado de suporte precisa.",
    )


class ErrorResponse(BaseModel):
    """🇺🇸 `{"error": {code, message, trace_id}}` — the one error shape of this API (`errors.py`).

    🇧🇷 `{"error": {code, message, trace_id}}` — a única forma de erro desta API (`errors.py`).
    """

    model_config = ConfigDict(frozen=True)

    error: ErrorDetail


class SessionInfo(BaseModel):
    """🇺🇸 Response of `GET /v1/session`: what this process is, plus who is asking.

    🇧🇷 Resposta de `GET /v1/session`: o que este processo é, mais quem está perguntando.
    """

    model_config = ConfigDict(frozen=True)

    workspace_id: str
    account_id: str
    security_groups: list[str]
    client: ClientIdentityView
