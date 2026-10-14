"""Request/response shapes that exist only at the HTTP boundary and are never reused by the SDK.

`diagnos`'s own models (`PatientRecord`, `ExamRecord`, `DocumentIndex`, `DriveNode`, `Page`) are returned to callers
exactly as the SDK produces them (`CONVENTIONS.md`: reuse, never reimplement). The types below are the thin envelopes
an HTTP body needs around them: a create call bundles a record with the `security_group` it belongs to, and a listing
of drive nodes needs each node's name decrypted alongside it. None of this belongs in the SDK, because none of it means
anything outside of "a JSON body arrived over HTTP".
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from diagnos import DriveNode, ExamRecord, PatientRecord

_EXPECT = "The `latest_version_id` you read; the write is refused with 409 if another version was saved since."


class PatientCreateRequest(BaseModel):
    """Body of `POST /v1/patients`."""

    model_config = ConfigDict(extra="forbid")

    record: PatientRecord
    security_group: str = Field(min_length=1, description="The one group the patient belongs to.")
    tags: list[str] = Field(default_factory=list, description="Sealed list labels.")
    specialist_ids: list[str] | None = None


class PatientUpdateRequest(BaseModel):
    """Body of `PUT /v1/patients/{id}`: a complete new record."""

    model_config = ConfigDict(extra="forbid")

    record: PatientRecord
    tags: list[str] | None = Field(default=None, description="`null` keeps the tags.")
    specialist_ids: list[str] | None = None
    expected_latest_version_id: str | None = Field(default=None, description=_EXPECT)


class ExamCreateRequest(BaseModel):
    """Body of `POST /v1/exams`."""

    model_config = ConfigDict(extra="forbid")

    record: ExamRecord
    patient_id: str = Field(min_length=1)
    security_group: str = Field(min_length=1)


class ExamUpdateRequest(BaseModel):
    """Body of `PUT /v1/exams/{id}`: a complete new record."""

    model_config = ConfigDict(extra="forbid")

    record: ExamRecord
    expected_latest_version_id: str | None = Field(default=None, description=_EXPECT)


class NodeView(BaseModel):
    """One drive node plus its decrypted name; `DriveNode` alone keeps the name sealed."""

    model_config = ConfigDict(frozen=True)

    node: DriveNode
    name: str | None = None


class FolderCreateRequest(BaseModel):
    """Body of `POST /v1/drives/{sg}/folders`."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Sealed before it leaves.")
    parent_id: str | None = Field(default=None, description="Parent folder node id.")


class FolderCreated(BaseModel):
    """A new folder's node id; folders have no content, so there is nothing else to report."""

    model_config = ConfigDict(frozen=True)

    node_id: str


class ClientIdentityView(BaseModel):
    """The mTLS identity of the caller, as `GET /v1/session` reports it."""

    model_config = ConfigDict(frozen=True)

    common_name: str
    serial: str


class ErrorDetail(BaseModel):
    """The body of every non-2xx response: what went wrong, for a program and for a person."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(description="Stable and machine-readable: branch on it, never on `message`.")
    message: str = Field(description="For a person; its wording may change.")
    trace_id: str | None = Field(
        default=None,
        description="The vault's trace id when the failure came from the vault, which is what a support ticket needs.",
    )


class ErrorResponse(BaseModel):
    """`{"error": {code, message, trace_id}}`, the one error shape of this API (`errors.py`)."""

    model_config = ConfigDict(frozen=True)

    error: ErrorDetail


class SessionInfo(BaseModel):
    """Response of `GET /v1/session`: what this process is, plus who is asking."""

    model_config = ConfigDict(frozen=True)

    workspace_id: str
    account_id: str
    security_groups: list[str]
    client: ClientIdentityView
