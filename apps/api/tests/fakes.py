"""A fake `Diagnos` (the SDK is never reached over the network here) and the `TestClient` wired to it.

Every fake resource below only has to satisfy the same duck-typed shape that the `diagnos.api.deps.get_vault`
dependency hands to the routers. The real `Diagnos`, `Patients`, `Exams` and `Drives` classes are never subclassed or
imported for their behavior; only their public method signatures are mirrored (`apps/sdk/src/diagnos/resources/*.py`).
That keeps these tests exercising exactly one thing: this package's own HTTP, mTLS and error wiring, never the SDK's.

The fakes live in their own module, imported into `conftest.py` (which re-exports everything below, fixtures
included), because they are large enough to earn one; `conftest.py` is just the file pytest always loads first. The
drive and node fakes (`FakeDrive`, `FakeDrives`) live in `fakes_drives.py` and are imported here only for the default
of `FakeDiagnos.drives`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from diagnos import (
    DocumentIndex,
    DocumentListItem,
    Exam,
    ExamRecord,
    ExamSummary,
    NotFoundError,
    Page,
    Patient,
    PatientRecord,
    PatientSummary,
)
from diagnos.api.app import create_app
from diagnos.api.mtls import ClientIdentity
from diagnos.api.settings import ApiSettings

from fakes_drives import FakeDrive, FakeDrives  # noqa: F401 — re-exported for `conftest.py`

WORKSPACE_ID = "ws_test"

# The identity every mTLS-gated test uses, unless it deliberately omits `trusted_test_identity` to exercise the "no
# certificate" path (`test_mtls.py`). See `mtls.require_client_certificate` for why that parameter exists only in tests.
TRUSTED_IDENTITY = ClientIdentity(common_name="ci-client", serial="01")


def _index(document_id: str, *, resource: str, security_group_id: str, **extra: Any) -> DocumentIndex:
    """Builds a vault-shaped `DocumentIndex` with one committed version, for the fakes below to hand back."""
    return DocumentIndex.model_validate(
        {
            "document_id": document_id,
            "workspace_id": WORKSPACE_ID,
            "resource": resource,
            "security_group_id": security_group_id,
            "encrypted_keys": {},
            "streams": {
                "data": {
                    "latest_version_id": "v1",
                    "versions": [
                        {"version_id": "v1", "size": 100, "created_at": "2024-01-01T00:00:00Z", "created_by": "t"}
                    ],
                    "pending_version_id": None,
                }
            },
            "created_at": "2024-01-01T00:00:00Z",
            "created_by": "tester",
            "updated_at": "2024-01-01T00:00:00Z",
            **extra,
        }
    )


class FakePatients:
    """Enough of `Patients` (`apps/sdk/src/diagnos/resources/patients.py`) for the routes in `routers/patients.py`.

    It is stateful on purpose (a create followed by a get must return what was created), and `calls` records every
    keyword the routes forwarded, so a test can assert the HTTP to SDK mapping without a real vault.
    """

    def __init__(self) -> None:
        """Starts empty. `raise_on_create` lets a test force a specific `diagnos` error out of `create`."""
        self._by_id: dict[str, Patient] = {}
        self._counter = 0
        self.raise_on_create: Exception | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list(self, **kwargs: Any) -> Page[DocumentListItem[PatientSummary]]:
        """Returns every stored patient with its summary, unfiltered."""
        self.calls.append(("list", kwargs))
        items = [DocumentListItem[PatientSummary](index=p.index, summary=p.summary) for p in self._by_id.values()]
        return Page(items=items, next_cursor=None)

    def create(self, record: PatientRecord, **kwargs: Any) -> Patient:
        """Stores `record` under a freshly minted id, or raises `raise_on_create` if a test set one."""
        self.calls.append(("create", kwargs))
        if self.raise_on_create is not None:
            raise self.raise_on_create
        self._counter += 1
        patient_id = f"patient_{self._counter}"
        index = _index(patient_id, resource="patients", security_group_id=kwargs["security_group"])
        patient = Patient(
            index=index, record=record, summary=PatientSummary.of(record, kwargs.get("tags", ())), version_id="v1"
        )
        self._by_id[patient_id] = patient
        return patient

    def get(self, patient_id: str, **kwargs: Any) -> Patient:
        """Returns the stored `Patient`, or raises `NotFoundError` as `Patients.get` does for an unknown id."""
        self.calls.append(("get", kwargs))
        return self._find(patient_id)

    def _find(self, patient_id: str) -> Patient:
        """Looks up a patient without recording a call."""
        try:
            return self._by_id[patient_id]
        except KeyError:
            raise NotFoundError(code="DocumentNotFound", message=f"no patient {patient_id!r}", status=404) from None

    def update(self, patient_id: str, record: PatientRecord, **kwargs: Any) -> Patient:
        """Replaces the stored record and keeps the same index."""
        self.calls.append(("update", kwargs))
        current = self._find(patient_id)
        updated = current.model_copy(update={"record": record})
        self._by_id[patient_id] = updated
        return updated

    def _flag(self, patient_id: str, **flags: bool) -> DocumentIndex:
        """Applies a flag to the stored index."""
        current = self._find(patient_id)
        index = current.index.model_copy(update=flags)
        self._by_id[patient_id] = current.model_copy(update={"index": index})
        return index

    def archive(self, patient_id: str) -> DocumentIndex:
        """Sets `is_archived`."""
        return self._flag(patient_id, is_archived=True)

    def unarchive(self, patient_id: str) -> DocumentIndex:
        """Clears `is_archived`."""
        return self._flag(patient_id, is_archived=False)

    def delete(self, patient_id: str) -> DocumentIndex:
        """Sets `is_deleted`."""
        return self._flag(patient_id, is_deleted=True)

    def restore(self, patient_id: str) -> DocumentIndex:
        """Clears `is_deleted`."""
        return self._flag(patient_id, is_deleted=False)


class FakeExams:
    """Enough of `Exams` (`apps/sdk/src/diagnos/resources/exams.py`) for the routes in `routers/exams.py`."""

    def __init__(self) -> None:
        """Starts empty."""
        self._by_id: dict[str, Exam] = {}
        self._counter = 0
        self.raise_on_create: Exception | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list(self, **kwargs: Any) -> Page[DocumentListItem[ExamSummary]]:
        """Returns every stored exam with its summary."""
        self.calls.append(("list", kwargs))
        items = [DocumentListItem[ExamSummary](index=e.index, summary=e.summary) for e in self._by_id.values()]
        return Page(items=items, next_cursor=None)

    def create(self, record: ExamRecord, *, patient_id: str, security_group: str) -> Exam:
        """Stores `record`, linking only `patient_id` into the clear `meta` as `Exams.create` does."""
        self.calls.append(("create", {"patient_id": patient_id, "security_group": security_group}))
        if self.raise_on_create is not None:
            raise self.raise_on_create
        self._counter += 1
        exam_id = f"exam_{self._counter}"
        index = _index(exam_id, resource="exams", security_group_id=security_group, meta={"patient_id": patient_id})
        exam = Exam(index=index, record=record, summary=ExamSummary.of(record), version_id="v1")
        self._by_id[exam_id] = exam
        return exam

    def get(self, exam_id: str, **kwargs: Any) -> Exam:
        """Returns the stored `Exam`, or raises `NotFoundError`."""
        self.calls.append(("get", kwargs))
        return self._find(exam_id)

    def _find(self, exam_id: str) -> Exam:
        """Looks up an exam without recording a call."""
        try:
            return self._by_id[exam_id]
        except KeyError:
            raise NotFoundError(code="DocumentNotFound", message=f"no exam {exam_id!r}", status=404) from None

    def update(self, exam_id: str, record: ExamRecord, **kwargs: Any) -> Exam:
        """Replaces the stored record."""
        self.calls.append(("update", kwargs))
        current = self._find(exam_id)
        updated = current.model_copy(update={"record": record, "summary": ExamSummary.of(record)})
        self._by_id[exam_id] = updated
        return updated

    def _flag(self, exam_id: str, **flags: bool) -> DocumentIndex:
        """Applies a flag to the stored index."""
        current = self._find(exam_id)
        index = current.index.model_copy(update=flags)
        self._by_id[exam_id] = current.model_copy(update={"index": index})
        return index

    def archive(self, exam_id: str) -> DocumentIndex:
        """Sets `is_archived`."""
        return self._flag(exam_id, is_archived=True)

    def unarchive(self, exam_id: str) -> DocumentIndex:
        """Clears `is_archived`."""
        return self._flag(exam_id, is_archived=False)

    def delete(self, exam_id: str) -> DocumentIndex:
        """Sets `is_deleted`."""
        return self._flag(exam_id, is_deleted=True)

    def restore(self, exam_id: str) -> DocumentIndex:
        """Clears `is_deleted`."""
        return self._flag(exam_id, is_deleted=False)


@dataclass
class FakeDiagnos:
    """Stands in for `Diagnos` (SDK `client.py`) with a fixed identity, in-memory resources and a counted lifecycle."""

    workspace_id: str = WORKSPACE_ID
    account_id: str = "acc_test"
    security_groups: list[str] = field(default_factory=lambda: ["sg1", "sg2"])
    patients: FakePatients = field(default_factory=FakePatients)
    exams: FakeExams = field(default_factory=FakeExams)
    drives: FakeDrives = field(default_factory=FakeDrives)
    unlock_calls: int = 0
    close_calls: int = 0
    lock_calls: int = 0

    def unlock(self) -> None:
        """Counts the call; a fake session needs no real enrollment."""
        self.unlock_calls += 1

    def close(self) -> None:
        """Counts the call."""
        self.close_calls += 1

    def lock(self) -> None:
        """Counts the call."""
        self.lock_calls += 1


@pytest.fixture
def fake_vault() -> FakeDiagnos:
    """Returns a fresh, empty `FakeDiagnos` for each test."""
    return FakeDiagnos()


@pytest.fixture
def api_settings() -> ApiSettings:
    """Returns mTLS paths that never have to exist on disk, because `create_app` never opens them itself.

    Only `ssl_config_for_uvicorn` (exercised in `test_mtls.py` as a plain dict, never fed to a real `ssl.SSLContext`)
    and the real `uvicorn.run` in `main.py` read these paths, so building an app for tests never touches the filesystem
    for them.
    """
    return ApiSettings(mtls_ca_file="/ca.pem", tls_cert_file="/tls.pem", tls_key_file="/tls-key.pem")


def build_app(
    fake_vault: FakeDiagnos,
    api_settings: ApiSettings,
    *,
    trusted_test_identity: ClientIdentity | None = TRUSTED_IDENTITY,
) -> FastAPI:
    """Builds `create_app` over `fake_vault`, authenticated as `TRUSTED_IDENTITY` unless the caller passes `None`."""
    return create_app(api_settings, fake_vault, trusted_test_identity=trusted_test_identity)


@pytest.fixture
def client(fake_vault: FakeDiagnos, api_settings: ApiSettings) -> Iterator[TestClient]:
    """Yields a `TestClient` authenticated as `TRUSTED_IDENTITY`, the common starting point of every route test."""
    with TestClient(build_app(fake_vault, api_settings)) as test_client:
        yield test_client
